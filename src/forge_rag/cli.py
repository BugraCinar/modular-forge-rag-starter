import argparse
import base64
import json
import os
import secrets
import signal
import threading
import time
from pathlib import Path

from forge_rag.shared.config import Settings


def init_env(path: Path):
    keys = {
        issuer: base64.b64encode(secrets.token_bytes(32)).decode()
        for issuer in ("forge-fastapi", "forge-spring")
    }
    contents = (
        f"DELEGATION_KEYS='{json.dumps(keys)}'\n"
        "DATABASE_URL=sqlite:///./data/rag.db\n"
        f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"
        "EMBEDDING_PROVIDER=hash\nEMBEDDING_DIMENSIONS=256\nGENERATION_PROVIDER=extractive\n"
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(contents)
    print(f"Created {path}. Copy each backend's delegation key into its private configuration.")


def main():
    parser = argparse.ArgumentParser(prog="forge-rag")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init-env")
    init.add_argument("--path", type=Path, default=Path(".env"))
    sub.add_parser("migrate")
    worker = sub.add_parser("worker")
    worker.add_argument("--once", action="store_true")
    sub.add_parser("demo")
    sub.add_parser("evaluate")
    purge = sub.add_parser("purge-jobs")
    purge.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    if args.command == "init-env":
        init_env(args.path)
        return
    settings = Settings()
    if args.command in {"migrate", "purge-jobs"}:
        from forge_rag.persistence.store import SQLRepository

        repository = SQLRepository(settings)
        try:
            if args.command == "migrate":
                repository.migrate()
                print("Schema version 1 ready.")
            else:
                if args.days < 1:
                    parser.error("--days must be positive")
                print(
                    f"Purged {repository.purge_jobs(time.time() - args.days * 86400)} terminal job records."
                )
        finally:
            repository.close()
        return
    if args.command in {"demo", "evaluate"}:
        if not settings.module_evaluation_enabled:
            parser.error("Evaluation module is disabled")
        from forge_rag.evaluation.runner import demo, evaluate

        print(
            json.dumps(
                demo() if args.command == "demo" else evaluate(), indent=2, ensure_ascii=False
            )
        )
        return
    if not settings.module_ingestion_enabled:
        parser.error("Ingestion module is disabled")
    from forge_rag.runtime import build_runtime

    runtime = build_runtime(settings)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    try:
        if not runtime.repository.ready():
            parser.error("Schema is not ready; run forge-rag migrate")
        assert runtime.worker is not None  # noqa: S101
        if args.once:
            runtime.worker.once()
        else:
            while not stop.is_set():
                if not runtime.worker.once():
                    stop.wait(1)
    finally:
        runtime.close()
