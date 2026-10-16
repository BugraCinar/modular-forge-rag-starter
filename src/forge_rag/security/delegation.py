import time
import uuid

import jwt

from forge_rag.shared.config import Settings
from forge_rag.shared.errors import RagError
from forge_rag.shared.models import Principal


def issue_token(key: bytes, principal: Principal, audience: str = "modular-forge-rag") -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": principal.issuer,
            "sub": principal.subject,
            "tenant": principal.tenant,
            "groups": list(principal.groups),
            "scope": list(principal.scopes),
            "aud": audience,
            "iat": now,
            "nbf": now,
            "exp": now + 60,
            "jti": str(uuid.uuid4()),
            "type": "rag-delegation",
        },
        key,
        algorithm="HS256",
        headers={"typ": "rag-delegation+jwt"},
    )


def verify_token(settings: Settings, token: str) -> Principal:
    try:
        if len(token) > 8192:
            raise ValueError("Token too large")
        unverified = jwt.decode(token, options={"verify_signature": False})
        issuer = unverified.get("iss")
        if not isinstance(issuer, str) or issuer not in settings.delegation_keys:
            raise ValueError("Unknown issuer")
        claims = jwt.decode(
            token,
            settings.key(issuer),
            algorithms=["HS256"],
            issuer=issuer,
            audience=settings.delegation_audience,
            options={
                "require": [
                    "iss",
                    "sub",
                    "aud",
                    "iat",
                    "nbf",
                    "exp",
                    "jti",
                    "tenant",
                    "scope",
                    "groups",
                    "type",
                ]
            },
        )
        if (
            jwt.get_unverified_header(token).get("typ") != "rag-delegation+jwt"
            or claims["type"] != "rag-delegation"
        ):
            raise ValueError("Wrong token type")
        if any(type(claims[name]) is not int for name in ("iat", "nbf", "exp")):
            raise ValueError("Invalid timestamps")
        if not 0 < claims["exp"] - claims["iat"] <= 60:
            raise ValueError("Excessive delegation lifetime")
        for field in ("sub", "tenant", "jti"):
            if not isinstance(claims[field], str) or not 1 <= len(claims[field]) <= 200:
                raise ValueError("Invalid identity")
        for field in ("groups", "scope"):
            if not isinstance(claims[field], list) or len(claims[field]) > 100:
                raise ValueError("Invalid authorization context")
            if any(
                not isinstance(item, str) or not 1 <= len(item) <= 200 for item in claims[field]
            ):
                raise ValueError("Invalid authorization item")
        if not set(claims["scope"]) <= {"rag:read", "rag:write"}:
            raise ValueError("Unknown scope")
        return Principal(
            issuer, claims["sub"], claims["tenant"], tuple(claims["groups"]), tuple(claims["scope"])
        )
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise RagError(401, "unauthorized", "Valid backend delegation is required.") from exc
