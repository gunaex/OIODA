"""
Conductor Again — Authentication
JWT access tokens + opaque refresh tokens with rotation.
Matches PM Again auth pattern.
"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_master_db
from app.models import RefreshToken, User

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user: User, db: Session) -> str:
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    db.commit()
    return raw


def rotate_refresh_token(old_raw: str, user: User, db: Session) -> str:
    old_hash = hashlib.sha256(old_raw.encode()).hexdigest()
    existing = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == old_hash,
            RefreshToken.revoked_at.is_(None),
        )
        .first()
    )
    if existing:
        existing.revoked_at = datetime.now(timezone.utc)
        db.commit()

    return create_refresh_token(user, db)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(
    request: Request,
    db: Session = Depends(get_master_db),
    authorization: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    token = None

    # Try cookie first
    if request.cookies.get("access_token"):
        token = request.cookies["access_token"]
    # Then Authorization header
    elif authorization:
        token = authorization.credentials

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # 1) Standalone local session JWT (HS256, issued by this service).
    try:
        payload = decode_access_token(token)
        if payload.get("type") == "access":
            user = db.query(User).filter(User.id == payload["sub"]).first()
            if user and user.active:
                return user
    except HTTPException:
        pass  # Not a valid local token — fall through to ecosystem SSO.

    # 2) Ecosystem SSO: a signed Account Again human identity token.
    # Authorization remains service-owned — map the verified human to the
    # local user by email and apply the LOCAL role.
    try:
        from app.integration.account_again_client import verify_ecosystem_identity_token

        claims = verify_ecosystem_identity_token(token)
        user = db.query(User).filter(User.email == claims.get("email")).first()
        if user and user.active:
            return user
    except Exception:
        pass

    raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(*roles: str):
    """Dependency factory: restrict to specific roles."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency


def set_auth_cookies(response, access_token: str, refresh_token: str, secure: bool):
    access_max = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_max = REFRESH_TOKEN_EXPIRE_DAYS * 86400

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
        path="/",
        max_age=access_max,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
        path="/api/auth",
        max_age=refresh_max,
    )


def clear_auth_cookies(response):
    response.set_cookie("access_token", "", httponly=True, path="/", max_age=0)
    response.set_cookie("refresh_token", "", httponly=True, path="/api/auth", max_age=0)
