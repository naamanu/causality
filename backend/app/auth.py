from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import Cookie, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .db import Workspace, get_db


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str
    workspace_id: str
    external_org_id: str
    role: str


serializer = URLSafeTimedSerializer(settings.session_secret, salt="causality-session-v1")


def encode_session(p: Principal) -> str:
    return serializer.dumps(p.__dict__)


def decode_session(value: str) -> Principal:
    try:
        data = serializer.loads(value, max_age=3600)
        return Principal(**data)
    except (BadSignature, SignatureExpired, TypeError) as exc:
        raise HTTPException(401, "invalid or expired session") from exc


def _dev_principal(db: Session) -> Principal:
    ws = db.scalar(select(Workspace).where(Workspace.external_org_id == "dev-org"))
    if ws is None:
        try:
            with db.begin_nested():
                ws = Workspace(external_org_id="dev-org", name="Local development")
                db.add(ws)
                db.flush()
        except IntegrityError:
            ws = db.scalar(select(Workspace).where(Workspace.external_org_id == "dev-org"))
    return Principal("dev-user", "dev@localhost", ws.id, ws.external_org_id, "owner")


def current_principal(
    causality_session: str | None = Cookie(default=None), db: Session = Depends(get_db)
) -> Principal:
    if causality_session:
        principal = decode_session(causality_session)
        if db.get(Workspace, principal.workspace_id) is None:
            raise HTTPException(401, "workspace no longer exists")
        return principal
    if not settings.production and settings.dev_auth_enabled:
        return _dev_principal(db)
    raise HTTPException(401, "authentication required")


def require_admin(p: Principal = Depends(current_principal)) -> Principal:
    if p.role not in {"owner", "admin"}:
        raise HTTPException(403, "workspace administrator required")
    return p


def login_redirect() -> RedirectResponse:
    if not settings.workos_client_id:
        raise HTTPException(503, "WorkOS is not configured")
    params = {
        "client_id": settings.workos_client_id,
        "redirect_uri": f"{settings.app_base_url}/api/v1/auth/callback",
        "response_type": "code",
        "provider": "authkit",
    }
    return RedirectResponse("https://api.workos.com/user_management/authorize?" + urlencode(params))


def exchange_code(code: str) -> dict:
    response = httpx.post(
        "https://api.workos.com/user_management/authenticate",
        headers={"Authorization": f"Bearer {settings.workos_api_key}"},
        json={
            "client_id": settings.workos_client_id,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def principal_from_workos(payload: dict, db: Session) -> Principal:
    access_token = payload.get("access_token", "")
    try:
        key = jwt.PyJWKClient(f"https://api.workos.com/sso/jwks/{settings.workos_client_id}").get_signing_key_from_jwt(access_token)
        claims = jwt.decode(access_token, key.key, algorithms=["RS256"], issuer="https://api.workos.com/", options={"verify_aud": False})
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "invalid identity token") from exc
    org_id = claims.get("org_id")
    user = payload.get("user") or {}
    if not org_id:
        raise HTTPException(403, "select or join an organization before continuing")
    ws = db.scalar(select(Workspace).where(Workspace.external_org_id == org_id))
    if ws is None:
        try:
            with db.begin_nested():
                ws = Workspace(external_org_id=org_id, name=claims.get("organization_name") or "Workspace")
                db.add(ws)
                db.flush()
        except IntegrityError:
            ws = db.scalar(select(Workspace).where(Workspace.external_org_id == org_id))
    return Principal(
        user_id=str(user.get("id") or claims["sub"]),
        email=str(user.get("email") or claims.get("email") or ""),
        workspace_id=ws.id,
        external_org_id=org_id,
        role=str(claims.get("role") or "member").removeprefix("org:"),
    )
