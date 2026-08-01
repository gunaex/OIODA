from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    must_change_password: bool

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    name: str
    external_project_url: Optional[str] = None


class ProjectArchiveRequest(BaseModel):
    archived: bool
    password: str


class ProjectDeleteRequest(BaseModel):
    password: str


class ProjectOut(BaseModel):
    id: int
    name: str
    slug: str
    external_project_url: Optional[str] = None
    archived: bool
    created_at: datetime

    class Config:
        from_attributes = True
