"""
Conductor Again — Auth Router
Login, logout, refresh, me, change password.
"""

import os

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.auth import (
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_current_user,
    hash_password,
    rotate_refresh_token,
    set_auth_cookies,
    verify_password,
)
from app.database import get_master_db
from app.models import User
from app.rate_limit import limiter
from app.schemas import ChangePasswordRequest, LoginRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"


@router.post("/login")
@limiter.limit("10/minute")
def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_master_db),
):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user, db)
    set_auth_cookies(response, access_token, refresh_token, COOKIE_SECURE)

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(response: Response):
    clear_auth_cookies(response)
    return {"message": "Logged out"}


@router.post("/refresh")
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_master_db),
    refresh_token: str | None = Cookie(default=None),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        payload = decode_access_token(request.cookies.get("access_token", ""))
        user_id = payload.get("sub")
    except HTTPException:
        # Access token expired — extract sub without verifying exp
        import jwt
        try:
            unverified = jwt.decode(
                request.cookies.get("access_token", ""),
                options={"verify_signature": False, "verify_exp": False},
            )
            user_id = unverified.get("sub")
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found")

    new_access = create_access_token(user)
    new_refresh = rotate_refresh_token(refresh_token, user, db)
    set_auth_cookies(response, new_access, new_refresh, COOKIE_SECURE)

    return {"access_token": new_access, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_master_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    db.commit()
    return {"message": "Password changed successfully"}
