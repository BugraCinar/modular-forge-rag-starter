import base64
import json
from importlib.resources import files
from typing import Any

from pydantic import SecretStr

from forge_rag.persistence.store import SQLRepository
from forge_rag.runtime import build_runtime
from forge_rag.shared.config import Settings
from forge_rag.shared.models import DocumentInput, Principal, QueryInput


def fixture():
    # Public fixture-only key, used exclusively by this in-memory offline runner.
    key = base64.b64encode(bytes(range(32))).decode()
    overrides: dict[str, Any] = {"_env_file": None}
    settings = Settings(
        **overrides,
        environment="development",
        delegation_keys={"evaluation": SecretStr(key)},
        database_url="sqlite:///:memory:",
        embedding_provider="hash",
        generation_provider="extractive",
        embedding_dimensions=256,
        module_pdf_enabled=False,
        module_ingestion_enabled=True,
    )
    repository = SQLRepository(settings)
    repository.migrate()
    runtime = build_runtime(settings, repository=repository)
    return runtime, Principal("evaluation", "reader", "offline-evaluation")


def demo():
    runtime, account = fixture()
    try:
        job = runtime.ingestion.enqueue(
            account,
            DocumentInput(
                external_id="welcome",
                title="Welcome",
                content="Modular Forge connects FastAPI and Spring Boot backends to a shared RAG service.",
            ),
            "demo-1",
        )
        runtime.worker.once()
        return {
            "job": runtime.repository.job(account, job["id"]),
            "response": runtime.query.answer(
                account, QueryInput(question="What does Modular Forge connect?")
            ),
        }
    finally:
        runtime.close()


def evaluate():
    fixture_data = json.loads(
        files("forge_rag.evaluation").joinpath("golden.json").read_text(encoding="utf-8")
    )
    runtime, account = fixture()
    try:
        ids = {}
        for item in fixture_data["documents"]:
            job = runtime.ingestion.enqueue(account, DocumentInput(**item), item["external_id"])
            ids[job["document_id"]] = item["external_id"]
            runtime.worker.once()
        recall, reciprocal, valid, faithful, abstain = [], [], [], [], []
        for case in fixture_data["cases"]:
            query = QueryInput(question=case["question"], top_k=3)
            hits = runtime.query.retrieve(account, query)
            answer = runtime.query.answer(account, query)
            if case["expected"]:
                ranks = [
                    rank
                    for rank, hit in enumerate(hits, start=1)
                    if ids[hit.document_id] == case["expected"]
                ]
                recall.append(bool(ranks))
                reciprocal.append(1 / min(ranks) if ranks else 0)
                cited_ids = {citation["chunk_id"] for citation in answer["citations"]}
                valid.append(
                    bool(answer["statements"])
                    and all(
                        set(statement["chunk_ids"]) <= cited_ids
                        for statement in answer["statements"]
                    )
                )
                faithful.append(case["answer_contains"] in answer["answer"])
            else:
                abstain.append(answer["status"] == "insufficient_evidence")
        metrics = {
            "recall_at_3": sum(recall) / len(recall),
            "mrr_at_3": sum(reciprocal) / len(reciprocal),
            "citation_validity": sum(valid) / len(valid),
            "fixture_answer_match": sum(faithful) / len(faithful),
            "unanswerable_abstention": sum(abstain) / len(abstain),
        }
        if any(value < 1 for value in metrics.values()):
            raise RuntimeError(f"Offline regression failed: {metrics}")
        return {
            "mode": "offline-regression",
            "cases": len(fixture_data["cases"]),
            "metrics": metrics,
            "note": "Small lexical fixture; not a semantic or LLM quality benchmark.",
        }
    finally:
        runtime.close()
