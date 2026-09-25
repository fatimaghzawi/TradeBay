
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.identity.password import validate_password


def _normalize_lebanon_phone(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned == "":
        return None
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    if digits.startswith("961"):
        digits = digits[3:]
    elif digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 8 or not digits.isdigit():
        raise ValueError("Phone must be +961 followed by exactly 8 digits")
    return f"+961{digits}"

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    business_name: str | None = Field(default=None, max_length=200)
    business_type: str | None = Field(default=None, max_length=20)
    invitation_token: str | None = Field(default=None, max_length=200)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)

    @field_validator("business_type")
    @classmethod
    def business_type_allowed(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = value.strip().lower()
        if normalized not in {"buyer", "supplier"}:
            raise ValueError("Choose whether your company buys or sells on TradeBay")
        return normalized

    @field_validator("invitation_token")
    @classmethod
    def invitation_token_clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

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
    avatar_url: str | None = None
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
    email_domain: str | None = None
    logo_url: str | None = None
    cover_url: str | None = None
    address: AddressInput | None = None
    description: str | None = None
    website: str | None = None
    year_established: int | None = None
    company_size: str | None = None
    industry_categories: list[str] | None = None
    business_tags: list[str] | None = None
    verification_status: str | None = None
    verification_documents: list[dict[str, object]] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

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
    email_domain: str | None = Field(default=None, max_length=253)
    address: AddressInput | None = None

    @field_validator("contact_phone")
    @classmethod
    def lebanon_phone(cls, value: str | None) -> str | None:
        return _normalize_lebanon_phone(value)

    @field_validator("email_domain")
    @classmethod
    def company_domain(cls, value: str | None) -> str | None:
        from app.modules.identity.company_domain import validate_company_email_domain

        if value is None or not str(value).strip():
            return None
        return validate_company_email_domain(value)

class SwitchBusinessRequest(BaseModel):
    business_id: str = Field(min_length=24, max_length=24)

class VerifyEmailRequest(BaseModel):

    token: str = Field(min_length=6, max_length=64)
    email: EmailStr | None = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):

    email: EmailStr
    token: str = Field(min_length=6, max_length=64)
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
    company_email: EmailStr | None = None
    role_id: str = Field(min_length=24, max_length=24)
    """Permission codes to grant (required; must be a subset of the role and the inviter)."""
    permissions: list[str] = Field(min_length=1)

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

class PlatformCreateUserRequest(BaseModel):

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)

class PlatformCreateTradingBusinessRequest(BaseModel):

    account_type: str = Field(min_length=5, max_length=20)
    business_name: str = Field(min_length=1, max_length=200)
    owner_email: EmailStr
    owner_password: str = Field(min_length=8, max_length=128)
    owner_first_name: str = Field(min_length=1, max_length=100)
    owner_last_name: str = Field(min_length=1, max_length=100)
    email_domain: str | None = Field(default=None, max_length=253)
    legal_name: str | None = Field(default=None, max_length=200)
    tax_number: str | None = Field(default=None, max_length=64)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    verify_supplier: bool = True

    @field_validator("owner_password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return validate_password(value)

    @field_validator("account_type")
    @classmethod
    def account_type_allowed(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"buyer", "supplier"}:
            raise ValueError("account_type must be buyer or supplier")
        return normalized

    @field_validator("contact_phone")
    @classmethod
    def lebanon_phone(cls, value: str | None) -> str | None:
        return _normalize_lebanon_phone(value)

    @field_validator("email_domain")
    @classmethod
    def company_domain(cls, value: str | None) -> str | None:
        from app.modules.identity.company_domain import validate_company_email_domain

        if value is None or not str(value).strip():
            return None
        return validate_company_email_domain(value)

class SuspendMembershipRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

class UpdateProfileRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)

class UpdateBusinessRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    legal_name: str | None = None
    tax_number: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    address: AddressInput | None = None
    email_domain: str | None = Field(default=None, max_length=253)
    description: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=300)
    year_established: int | None = Field(default=None, ge=1800, le=2100)
    company_size: str | None = Field(default=None, max_length=64)
    industry_categories: list[str] | None = Field(default=None, max_length=12)
    business_tags: list[str] | None = Field(default=None, max_length=12)

    @field_validator("contact_phone")
    @classmethod
    def lebanon_phone(cls, value: str | None) -> str | None:
        return _normalize_lebanon_phone(value)

    @field_validator("email_domain")
    @classmethod
    def company_domain(cls, value: str | None) -> str | None:
        from app.modules.identity.company_domain import validate_company_email_domain

        if value is None or not str(value).strip():
            return None
        return validate_company_email_domain(value)

    @field_validator("industry_categories", "business_tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned: list[str] = []
        for item in value:
            label = item.strip()
            if label and label not in cleaned and len(label) <= 48:
                cleaned.append(label)
        return cleaned[:12]

class VerificationDocumentInput(BaseModel):
    document_type: str = Field(min_length=1, max_length=64)
    file_name: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None, max_length=1000)

class SubmitSupplierVerificationRequest(BaseModel):
    documents: list[VerificationDocumentInput] = Field(min_length=3, max_length=10)

class ReviewSupplierVerificationRequest(BaseModel):
    decision: str = Field(min_length=6, max_length=16)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("decision")
    @classmethod
    def decision_allowed(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"approve", "reject", "revoke"}:
            raise ValueError("decision must be approve, reject, or revoke")
        return normalized

