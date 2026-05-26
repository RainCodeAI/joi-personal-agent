from __future__ import annotations

import secrets
from typing import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings


AUTH_EXEMPT_PATHS: tuple[str, ...] = (
    "/health",
    "/oauth/callback",
    "/docs",
    "/openapi.json",
    "/redoc",
)

AUTH_HEADER = "x-joi-api-token"
AUTH_QUERY_PARAM = "api_token"


def _path_is_exempt(path: str, exempt_paths: Iterable[str] = AUTH_EXEMPT_PATHS) -> bool:
    return any(path == exempt or path.startswith(f"{exempt}/") for exempt in exempt_paths)


async def require_local_api_token(request: Request, call_next):
    token = settings.joi_api_token
    if not token or _path_is_exempt(request.url.path):
        return await call_next(request)

    supplied = request.headers.get(AUTH_HEADER)
    if request.url.path == "/api/v2/events/stream":
        supplied = supplied or request.query_params.get(AUTH_QUERY_PARAM)

    if not supplied or not secrets.compare_digest(supplied, token):
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing or invalid Joi API token"},
        )

    return await call_next(request)
