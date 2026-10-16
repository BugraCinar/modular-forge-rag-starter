"""Initial schema. Freeze after v1.0.0; subsequent changes need a new migration."""

from sqlalchemy import (
    JSON,
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)


def schema(vector_type=JSON):
    meta = MetaData()
    Table("rag_schema", meta, Column("version", Integer, primary_key=True))
    docs = Table(
        "rag_documents",
        meta,
        Column("id", String(36), primary_key=True),
        Column("tenant", String(200), nullable=False),
        Column("dataset", String(64), nullable=False),
        Column("external_id", String(128), nullable=False),
        Column("owner", String(300), nullable=False),
        Column("title", String(256), nullable=False),
        Column("revision", Integer, nullable=False),
        Column("active_revision", Integer, nullable=False),
        Column("signature", String(256), nullable=False),
        Column("digest", String(64), nullable=False),
        Column("status", String(24), nullable=False),
        Column("created_at", Float, nullable=False),
        Column("updated_at", Float, nullable=False),
        UniqueConstraint("tenant", "dataset", "external_id"),
    )
    acl = Table(
        "rag_acl",
        meta,
        Column("document_id", String(36), primary_key=True),
        Column("kind", String(16), primary_key=True),
        Column("value", String(300), primary_key=True),
    )
    jobs = Table(
        "rag_jobs",
        meta,
        Column("id", String(36), primary_key=True),
        Column("document_id", String(36), nullable=False),
        Column("tenant", String(200), nullable=False),
        Column("owner", String(300), nullable=False),
        Column("idempotency_key", String(128), nullable=False),
        Column("digest", String(64), nullable=False),
        Column("revision", Integer, nullable=False),
        Column("signature", String(256), nullable=False),
        Column("payload", JSON, nullable=False),
        Column("status", String(24), nullable=False),
        Column("attempts", Integer, nullable=False),
        Column("available_at", Float, nullable=False),
        Column("lease_until", Float, nullable=False),
        Column("lease_token", String(36), nullable=False),
        Column("error_code", String(64), nullable=True),
        Column("created_at", Float, nullable=False),
        Column("updated_at", Float, nullable=False),
        UniqueConstraint("tenant", "owner", "idempotency_key"),
    )
    chunks = Table(
        "rag_chunks",
        meta,
        Column("id", String(36), primary_key=True),
        Column("document_id", String(36), nullable=False),
        Column("revision", Integer, nullable=False),
        Column("signature", String(256), nullable=False),
        Column("text", Text, nullable=False),
        Column("position", Integer, nullable=False),
        Column("page", Integer, nullable=True),
        Column("start", Integer, nullable=False),
        Column("end", Integer, nullable=False),
        Column("embedding", vector_type, nullable=False),
    )
    Index("ix_rag_documents_scope", docs.c.tenant, docs.c.dataset, docs.c.signature)
    Index("ix_rag_acl_document", acl.c.document_id)
    Index("ix_rag_jobs_claim", jobs.c.status, jobs.c.available_at, jobs.c.lease_until)
    Index("ix_rag_chunks_document", chunks.c.document_id, chunks.c.revision)
    return meta
