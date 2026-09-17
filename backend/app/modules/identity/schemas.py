"""Identity API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.identity.password import validate_password


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    business_name: str | None = Field(default=None, max_length=200)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)


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


class AddressInput(BaseModel):
    street: str | None = None
    city: str | None = None
    district: str | None = None
    governorate: str | None = None
    postal_code: str | None = None
    country: str | None = None


class BusinessPublic(BaseModel):
    id: str
    name: str
    type: str
    status: str
    legal_name: str | None = None
    tax_number: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address: AddressInput | None = None


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
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    address: AddressInput | None = None


class SwitchBusinessRequest(BaseModel):
    business_id: str = Field(min_length=24, max_length=24)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=8, max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=8, max_length=256)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)


class ResendVerificationRequest(BaseModel):
    email: EmailStr | None = None


class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role_id: str = Field(min_length=24, max_length=24)


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=8, max_length=256)


class UpdateMemberRoleRequest(BaseModel):
    role_id: str = Field(min_length=24, max_length=24)


class CreateRoleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    permissions: list[str] = Field(min_length=1)


class UpdateRoleRequest(BaseModel):
    permissions: list[str] = Field(min_length=1)


class SuspendUserRequest(BaseModel):
    user_id: str = Field(min_length=24, max_length=24)
    reason: str = Field(min_length=1, max_length=500)
