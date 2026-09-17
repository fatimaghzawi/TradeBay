"""Identity API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    business_name: str | None = Field(default=None, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    first_name: str
    last_name: str
    status: str
    email_verified_at: datetime | None = None


class BusinessPublic(BaseModel):
    id: str
    name: str
    type: str
    status: str


class MembershipPublic(BaseModel):
    id: str
    business_account_id: str
    role_id: str
    status: str


class AuthMeResponse(BaseModel):
    user: UserPublic
    active_business: BusinessPublic | None = None
    membership: MembershipPublic | None = None
    role_name: str | None = None
    permissions: list[str] = Field(default_factory=list)


class CreateBusinessRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(default="buyer")
    legal_name: str | None = None
    tax_number: str | None = None


class SwitchBusinessRequest(BaseModel):
    business_id: str = Field(min_length=24, max_length=24)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=8, max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=8, max_length=256)
    password: str = Field(min_length=8, max_length=128)


class TokenPairMeta(BaseModel):
    access_token_expires_in_minutes: int
