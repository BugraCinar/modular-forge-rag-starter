import threading

from forge_rag.shared.config import Settings
from forge_rag.shared.errors import InvalidDocument, ProviderError
from forge_rag.shared.ports import Chunker, Embedder, Extractor, Repository
from forge_rag.shared.vectors import validate_vectors


class Worker:
    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        extractor: Extractor,
        chunker: Chunker,
        embedder: Embedder,
        signature: str,
    ):
        self.settings, self.repository = settings, repository
        self.extractor, self.chunker, self.embedder, self.signature = (
            extractor,
            chunker,
            embedder,
            signature,
        )

    def once(self) -> bool:
        job = self.repository.claim(self.settings.job_lease_seconds)
        if job is None:
            return False
        stop, lost = threading.Event(), threading.Event()

        def heartbeat():
            while not stop.wait(min(self.settings.job_lease_seconds / 3, 10)):
                try:
                    if not self.repository.renew(job, self.settings.job_lease_seconds):
                        lost.set()
                        return
                except Exception:
                    lost.set()
                    return

        renewer = threading.Thread(target=heartbeat, daemon=True)
        renewer.start()
        try:
            if job["attempts"] > self.settings.job_max_attempts:
                self.repository.fail(
                    job, "attempts_exhausted", True, self.settings.job_max_attempts
                )
                return True
            if job["signature"] != self.signature:
                self.repository.fail(job, "pipeline_changed", True, self.settings.job_max_attempts)
                return True
            payload = job["payload"]
            pieces = self.chunker.split(
                self.extractor.extract(payload["content"], payload["media_type"])
            )
            vectors = []
            for offset in range(0, len(pieces), 32):
                batch = pieces[offset : offset + 32]
                values = validate_vectors(
                    self.embedder.embed([piece.text for piece in batch]),
                    len(batch),
                    self.embedder.dimensions,
                )
                vectors.extend(values)
                if lost.is_set():
                    raise ProviderError("Worker lost its lease")
            self.repository.publish(job, pieces, vectors)
        except InvalidDocument:
            self.repository.fail(job, "invalid_document", True, self.settings.job_max_attempts)
        except ProviderError:
            self.repository.fail(job, "provider_unavailable", False, self.settings.job_max_attempts)
        except Exception:
            # Persist a code only: provider/parser messages can contain source text or secrets.
            self.repository.fail(job, "processing_failed", False, self.settings.job_max_attempts)
        finally:
            stop.set()
            renewer.join()
        return True
