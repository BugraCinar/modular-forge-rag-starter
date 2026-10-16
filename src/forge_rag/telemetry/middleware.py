import logging
import time

logger = logging.getLogger("forge_rag.requests")


class TelemetryMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started, status = time.monotonic(), 500

        async def observed(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, observed)
        finally:
            logger.info(
                "request id=%s status=%d duration_ms=%.1f",
                scope.get("state", {}).get("request_id", ""),
                status,
                (time.monotonic() - started) * 1000,
            )
