import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    and_,
    create_engine,
    delete,
    exists,
    func,
    insert,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.pool import StaticPool

from forge_rag.persistence.migrations.v0001 import schema
from forge_rag.retrieval.scoring import bm25, cosine, query_terms
from forge_rag.shared.config import Settings
from forge_rag.shared.errors import RagError
from forge_rag.shared.models import DocumentInput, Hit, Piece, Principal


class SQLRepository:
    def __init__(self, settings: Settings):
        self.settings = settings
        url = make_url(settings.database_url)
        self.postgres = url.get_backend_name() == "postgresql"
        if url.get_backend_name() not in {"sqlite", "postgresql"}:
            raise ValueError("Only SQLite and PostgreSQL are supported")
        vector_type: Any = JSON
        if self.postgres:
            from pgvector.sqlalchemy import Vector

            vector_type = Vector()
        if url.get_backend_name() == "sqlite" and url.database not in {None, "", ":memory:"}:
            Path(str(url.database)).parent.mkdir(parents=True, exist_ok=True)
        options: dict[str, Any] = {"pool_pre_ping": True, "hide_parameters": True}
        if url.get_backend_name() == "sqlite":
            options["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if url.database in {None, "", ":memory:"}:
                options["poolclass"] = StaticPool
        self.engine = create_engine(settings.database_url, **options)
        self.meta = schema(vector_type)
        self.docs, self.acl, self.jobs, self.chunks = (
            self.meta.tables[name]
            for name in ("rag_documents", "rag_acl", "rag_jobs", "rag_chunks")
        )

    def migrate(self):
        with self.engine.begin() as connection:
            if self.postgres:
                connection.execute(text("SELECT pg_advisory_xact_lock(722410601)"))
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            self.meta.create_all(connection)
            versions = (
                connection.execute(select(self.meta.tables["rag_schema"].c.version)).scalars().all()
            )
            if versions and versions != [1]:
                raise RuntimeError("Unsupported schema version")
            if not versions:
                connection.execute(insert(self.meta.tables["rag_schema"]).values(version=1))

    def _scope(self, principal: Principal, *, owner=False):
        rules = [self.docs.c.tenant == principal.tenant]
        if owner:
            rules.append(self.docs.c.owner == principal.actor)
        else:
            permitted = or_(
                and_(self.acl.c.kind == "subject", self.acl.c.value == principal.actor),
                and_(self.acl.c.kind == "group", self.acl.c.value.in_(principal.groups)),
            )
            rules.append(
                or_(
                    self.docs.c.owner == principal.actor,
                    exists(select(1).where(self.acl.c.document_id == self.docs.c.id, permitted)),
                )
            )
        return and_(*rules)

    def enqueue(self, principal: Principal, request: DocumentInput, key: str, signature: str):
        payload = request.model_dump()
        digest = hashlib.sha256(
            json.dumps({"request": payload, "signature": signature}, sort_keys=True).encode()
        ).hexdigest()
        now = time.time()
        try:
            with self.engine.begin() as connection:
                previous = (
                    connection.execute(
                        select(self.jobs).where(
                            self.jobs.c.tenant == principal.tenant,
                            self.jobs.c.owner == principal.actor,
                            self.jobs.c.idempotency_key == key,
                        )
                    )
                    .mappings()
                    .first()
                )
                if previous:
                    if previous["digest"] != digest:
                        raise RagError(
                            409, "idempotency_conflict", "This key belongs to a different request."
                        )
                    if previous["status"] == "deleted":
                        raise RagError(
                            410, "document_deleted", "The document for this request was deleted."
                        )
                    return self._job_public(dict(previous))
                query = select(self.docs).where(
                    self.docs.c.tenant == principal.tenant,
                    self.docs.c.dataset == request.dataset,
                    self.docs.c.external_id == request.external_id,
                )
                if self.postgres:
                    query = query.with_for_update()
                document = connection.execute(query).mappings().first()
                if document and document["owner"] != principal.actor:
                    raise RagError(404, "not_found", "Document not found.")
                document_id = document["id"] if document else str(uuid.uuid4())
                revision = document["revision"] + 1 if document else 1
                values = dict(
                    tenant=principal.tenant,
                    dataset=request.dataset,
                    external_id=request.external_id,
                    owner=principal.actor,
                    title=request.title,
                    revision=revision,
                    active_revision=0,
                    signature=signature,
                    digest=digest,
                    status="queued",
                    updated_at=now,
                )
                if document:
                    changed = connection.execute(
                        update(self.docs)
                        .where(
                            self.docs.c.id == document_id,
                            self.docs.c.revision == document["revision"],
                        )
                        .values(**values)
                    )
                    if changed.rowcount != 1:
                        raise RagError(
                            409, "concurrent_update", "Retry with the same idempotency key."
                        )
                    connection.execute(
                        update(self.jobs)
                        .where(
                            self.jobs.c.document_id == document_id,
                            self.jobs.c.status.in_(["queued", "running"]),
                        )
                        .values(status="superseded", payload={}, updated_at=now)
                    )
                else:
                    connection.execute(
                        insert(self.docs).values(id=document_id, created_at=now, **values)
                    )
                connection.execute(delete(self.acl).where(self.acl.c.document_id == document_id))
                entries = [
                    {"document_id": document_id, "kind": kind, "value": value}
                    for kind, values_list in (
                        ("subject", request.read_subjects),
                        ("group", request.read_groups),
                    )
                    for value in sorted(set(values_list))
                ]
                if entries:
                    connection.execute(insert(self.acl), entries)
                job = dict(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    tenant=principal.tenant,
                    owner=principal.actor,
                    idempotency_key=key,
                    digest=digest,
                    revision=revision,
                    signature=signature,
                    payload=payload,
                    status="queued",
                    attempts=0,
                    available_at=now,
                    lease_until=0,
                    lease_token="",
                    error_code=None,
                    created_at=now,
                    updated_at=now,
                )
                connection.execute(insert(self.jobs).values(**job))
                return self._job_public(job)
        except IntegrityError as exc:
            raise RagError(
                409, "concurrent_update", "Retry with the same idempotency key."
            ) from exc

    @staticmethod
    def _job_public(job):
        return {
            name: job[name]
            for name in ("id", "document_id", "revision", "status", "attempts", "error_code")
        }

    def document(self, principal: Principal, document_id: str):
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(self.docs).where(self.docs.c.id == document_id, self._scope(principal))
                )
                .mappings()
                .first()
            )
        if not row:
            raise RagError(404, "not_found", "Document not found.")
        return {
            name: row[name]
            for name in (
                "id",
                "external_id",
                "dataset",
                "title",
                "revision",
                "active_revision",
                "status",
            )
        }

    def job(self, principal: Principal, job_id: str):
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    select(self.jobs).where(
                        self.jobs.c.id == job_id,
                        self.jobs.c.tenant == principal.tenant,
                        self.jobs.c.owner == principal.actor,
                    )
                )
                .mappings()
                .first()
            )
        if not row:
            raise RagError(404, "not_found", "Job not found.")
        return self._job_public(dict(row))

    def claim(self, lease_seconds: int):
        now = time.time()
        eligible = or_(
            and_(self.jobs.c.status == "queued", self.jobs.c.available_at <= now),
            and_(self.jobs.c.status == "running", self.jobs.c.lease_until <= now),
        )
        with self.engine.begin() as connection:
            query = select(self.jobs).where(eligible).order_by(self.jobs.c.created_at).limit(1)
            if self.postgres:
                query = query.with_for_update(skip_locked=True)
            row = connection.execute(query).mappings().first()
            if not row:
                return None
            token = str(uuid.uuid4())
            changed = connection.execute(
                update(self.jobs)
                .where(self.jobs.c.id == row["id"], eligible)
                .values(
                    status="running",
                    lease_token=token,
                    lease_until=now + lease_seconds,
                    attempts=self.jobs.c.attempts + 1,
                    updated_at=now,
                )
            )
            if changed.rowcount != 1:
                return None
            return dict(
                row,
                status="running",
                lease_token=token,
                lease_until=now + lease_seconds,
                attempts=row["attempts"] + 1,
            )

    def _lease(self, job):
        return and_(
            self.jobs.c.id == job["id"],
            self.jobs.c.status == "running",
            self.jobs.c.lease_token == job["lease_token"],
            self.jobs.c.lease_until > time.time(),
        )

    def publish(self, job, pieces: list[Piece], vectors: list[list[float]]):
        now = time.time()
        with self.engine.begin() as connection:
            # Every mutating path locks document -> job, avoiding opposite-order deadlocks.
            document_query = select(self.docs.c.id).where(
                self.docs.c.id == job["document_id"], self.docs.c.revision == job["revision"]
            )
            if self.postgres:
                document_query = document_query.with_for_update()
            if connection.execute(document_query).first() is None:
                return False
            changed = connection.execute(
                update(self.jobs)
                .where(self._lease(job))
                .values(status="completed", payload={}, error_code=None, updated_at=now)
            )
            if changed.rowcount != 1:
                return False
            changed = connection.execute(
                update(self.docs)
                .where(
                    self.docs.c.id == job["document_id"], self.docs.c.revision == job["revision"]
                )
                .values(active_revision=job["revision"], status="ready", updated_at=now)
            )
            if changed.rowcount != 1:
                connection.execute(
                    update(self.jobs).where(self.jobs.c.id == job["id"]).values(status="superseded")
                )
                return False
            connection.execute(
                delete(self.chunks).where(self.chunks.c.document_id == job["document_id"])
            )
            connection.execute(
                insert(self.chunks),
                [
                    dict(
                        id=str(uuid.uuid4()),
                        document_id=job["document_id"],
                        revision=job["revision"],
                        signature=job["signature"],
                        text=piece.text,
                        position=piece.position,
                        page=piece.page,
                        start=piece.start,
                        end=piece.end,
                        embedding=vector,
                    )
                    for piece, vector in zip(pieces, vectors, strict=True)
                ],
            )
            return True

    def fail(self, job, code: str, permanent: bool, max_attempts: int):
        final = permanent or job["attempts"] >= max_attempts
        now = time.time()
        with self.engine.begin() as connection:
            document_query = select(self.docs.c.id).where(self.docs.c.id == job["document_id"])
            if self.postgres:
                document_query = document_query.with_for_update()
            connection.execute(document_query).first()
            values = dict(
                status="failed" if final else "queued",
                error_code=code,
                updated_at=now,
                lease_until=0,
                available_at=now + min(2 ** job["attempts"], 300),
            )
            if final:
                values["payload"] = {}
            changed = connection.execute(update(self.jobs).where(self._lease(job)).values(**values))
            if changed.rowcount and final:
                connection.execute(
                    update(self.docs)
                    .where(
                        self.docs.c.id == job["document_id"],
                        self.docs.c.revision == job["revision"],
                    )
                    .values(status="failed", updated_at=now)
                )

    def renew(self, job, lease_seconds: int):
        with self.engine.begin() as connection:
            result = connection.execute(
                update(self.jobs)
                .where(self._lease(job))
                .values(lease_until=time.time() + lease_seconds, updated_at=time.time())
            )
            return result.rowcount == 1

    def delete(self, principal: Principal, document_id: str):
        with self.engine.begin() as connection:
            changed = connection.execute(
                delete(self.docs).where(
                    self.docs.c.id == document_id, self._scope(principal, owner=True)
                )
            )
            if changed.rowcount != 1:
                raise RagError(404, "not_found", "Document not found.")
            connection.execute(delete(self.acl).where(self.acl.c.document_id == document_id))
            connection.execute(delete(self.chunks).where(self.chunks.c.document_id == document_id))
            connection.execute(
                update(self.jobs)
                .where(self.jobs.c.document_id == document_id)
                .values(status="deleted", payload={}, updated_at=time.time())
            )

    def _eligible(self, principal, dataset=None, signature=None):
        rules = [
            self._scope(principal),
            self.chunks.c.revision == self.docs.c.active_revision,
            self.docs.c.active_revision > 0,
        ]
        if dataset is not None:
            rules.append(self.docs.c.dataset == dataset)
        if signature is not None:
            rules.append(self.chunks.c.signature == signature)
        return and_(*rules)

    def search(
        self,
        principal: Principal,
        dataset: str,
        signature: str,
        vector: list[float],
        question: str,
        limit: int,
    ):
        query = (
            select(self.chunks, self.docs.c.title)
            .select_from(self.chunks.join(self.docs, self.chunks.c.document_id == self.docs.c.id))
            .where(self._eligible(principal, dataset, signature))
        )
        with self.engine.connect() as connection:
            if self.postgres:
                distance = self.chunks.c.embedding.cosine_distance(vector)
                vector_rows = (
                    connection.execute(
                        query.add_columns((1 - distance).label("similarity"))
                        .order_by(distance, self.chunks.c.id)
                        .limit(limit)
                    )
                    .mappings()
                    .all()
                )
                # SQL full-text search applies exactly the same tenant/ACL/revision predicates.
                document = func.to_tsvector("simple", self.chunks.c.text)
                search = func.plainto_tsquery("simple", " ".join(query_terms(question)))
                lexical_score = func.ts_rank_cd(document, search)
                lexical_rows = (
                    connection.execute(
                        query.add_columns(lexical_score.label("lexical"))
                        .where(document.op("@@")(search))
                        .order_by(lexical_score.desc(), self.chunks.c.id)
                        .limit(limit)
                    )
                    .mappings()
                    .all()
                )
                vector_rank = [(dict(row), float(row["similarity"])) for row in vector_rows]
                lexical_rank = [(dict(row), float(row["lexical"])) for row in lexical_rows]
            else:
                rows = (
                    connection.execute(
                        query.order_by(self.chunks.c.id).limit(self.settings.sqlite_max_chunks + 1)
                    )
                    .mappings()
                    .all()
                )
                if len(rows) > self.settings.sqlite_max_chunks:
                    raise RagError(503, "corpus_capacity", "Use PostgreSQL for this corpus size.")
                lexical = bm25(question, [row["text"] for row in rows])
                vector_rank = sorted(
                    [(dict(row), cosine(vector, row["embedding"])) for row in rows],
                    key=lambda pair: -pair[1],
                )[:limit]
                lexical_rank = sorted(
                    [
                        (dict(row), value)
                        for row, value in zip(rows, lexical, strict=True)
                        if value > 0
                    ],
                    key=lambda pair: -pair[1],
                )[:limit]
        merged: dict[str, Hit] = {}
        for name, ranking in (("similarity", vector_rank), ("lexical", lexical_rank)):
            for position, (row, score_value) in enumerate(ranking, start=1):
                hit = merged.setdefault(
                    row["id"],
                    Hit(
                        **{
                            field: row[field]
                            for field in (
                                "id",
                                "document_id",
                                "revision",
                                "title",
                                "text",
                                "position",
                                "page",
                                "start",
                                "end",
                            )
                        }
                    ),
                )
                setattr(hit, name, score_value)
                hit.score += 1 / (60 + position)
        return sorted(merged.values(), key=lambda hit: (-hit.score, hit.id))

    def still_allowed(self, principal: Principal, ids: list[str]):
        if not ids:
            return True
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(self.chunks.c.id)
                    .select_from(
                        self.chunks.join(self.docs, self.chunks.c.document_id == self.docs.c.id)
                    )
                    .where(self._eligible(principal), self.chunks.c.id.in_(ids))
                )
                .scalars()
                .all()
            )
        return set(rows) == set(ids)

    def purge_jobs(self, before: float):
        with self.engine.begin() as connection:
            result = connection.execute(
                delete(self.jobs).where(
                    self.jobs.c.status.in_(["completed", "failed", "superseded", "deleted"]),
                    self.jobs.c.updated_at < before,
                )
            )
            return result.rowcount

    def ready(self):
        try:
            with self.engine.connect() as connection:
                return connection.execute(
                    select(self.meta.tables["rag_schema"].c.version)
                ).scalars().all() == [1]
        except SQLAlchemyError:
            return False

    def close(self):
        self.engine.dispose()
