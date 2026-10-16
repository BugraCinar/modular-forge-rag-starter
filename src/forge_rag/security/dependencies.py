from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from forge_rag.security.delegation import verify_token
from forge_rag.shared.errors import RagError

bearer = HTTPBearer(auto_error=False)


def principal(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise RagError(401, "unauthorized", "Valid backend delegation is required.")
    return verify_token(request.app.state.rag.settings, credentials.credentials)


def reader(account=Depends(principal)):
    if "rag:read" not in account.scopes:
        raise RagError(403, "forbidden", "Read scope is required.")
    return account


def writer(account=Depends(principal)):
    if "rag:write" not in account.scopes:
        raise RagError(403, "forbidden", "Write scope is required.")
    return account
