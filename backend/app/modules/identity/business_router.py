"""Business account API routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile

from app.core.config import Settings, get_settings
from app.core.constants import ACCESS_COOKIE_NAME
from app.core.exceptions import BadRequestError
from app.modules.identity.constants import REQUIRED_SUPPLIER_DOCUMENT_TYPES
from app.modules.identity.dependencies import (
    AuthContext,
    get_auth_service,
    get_business_service,
    get_current_user,
    require_business_permission,
    require_business_scope,
    require_verification_document_access,
    require_verified_email,
)
from app.modules.identity.http import client_ip
from app.modules.identity.schemas import (
    CreateBusinessRequest,
    SubmitSupplierVerificationRequest,
    SwitchBusinessRequest,
    UpdateBusinessRequest,
)
from app.modules.identity.service import AuthService, BusinessService
from app.shared.schemas.response import paginated, success

businesses_router = APIRouter(prefix="/businesses", tags=["Businesses"])
companies_router = APIRouter(prefix="/companies", tags=["Companies"])


async def _switch_business_response(
    *,
    body: SwitchBusinessRequest,
    response: Response,
    auth: AuthContext,
    service: AuthService,
    settings: Settings,
) -> dict[str, Any]:
    result = await service.switch_business(
        session_id=auth.session_id,
        user_id=auth.user_id,
        business_id=body.business_id,
    )
    cookie: dict[str, Any] = {
        "httponly": True,
        "secure": settings.cookie_secure or settings.is_production,
        "samesite": settings.cookie_samesite,
        "path": "/",
        "max_age": settings.access_token_expire_minutes * 60,
    }
    if settings.cookie_domain:
        cookie["domain"] = settings.cookie_domain
    response.set_cookie(ACCESS_COOKIE_NAME, result["access_token"], **cookie)
    return success({"business": result["business"]})


@businesses_router.get("", summary="List businesses for current user")
async def list_businesses(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    items = await service.list_for_user(auth.user_id)
    return paginated(items, page=1, page_size=len(items) or 20, total=len(items))


@businesses_router.post("", summary="Create a business account for current user")
async def create_business(
    body: CreateBusinessRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_verified_email())],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    business = await service.create_for_user(
        user_id=auth.user_id,
        name=body.name,
        account_type=body.type,
        legal_name=body.legal_name,
        tax_number=body.tax_number,
        contact_email=str(body.contact_email) if body.contact_email else None,
        contact_phone=body.contact_phone,
        email_domain=body.email_domain,
        address=body.address.model_dump() if body.address else None,
        ip_address=client_ip(request),
    )
    return success(business)


@businesses_router.get("/current", summary="Get active business from session")
async def current_business(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    if auth.business_id is None:
        return success(None)
    payload = await service.get_for_user(user_id=auth.user_id, business_id=auth.business_id)
    return success(payload)


@businesses_router.post("/switch", summary="Switch the session's active business")
async def switch_business_brd(
    body: SwitchBusinessRequest,
    response: Response,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    return await _switch_business_response(
        body=body, response=response, auth=auth, service=service, settings=settings
    )


@businesses_router.post("/current/switch", summary="Switch active business (legacy)", include_in_schema=False)
async def switch_business_legacy(
    body: SwitchBusinessRequest,
    response: Response,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    return await _switch_business_response(
        body=body, response=response, auth=auth, service=service, settings=settings
    )


@companies_router.get("/{business_id}", summary="Public trading company profile")
async def get_public_company(
    business_id: str,
    auth: Annotated[AuthContext, Depends(get_current_user)],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    del auth
    payload = await service.get_public_company(business_id)
    return success(payload)


@businesses_router.get("/{business_id}", summary="Get a business the user belongs to")
async def get_business(
    business_id: str,
    auth: Annotated[AuthContext, Depends(require_business_scope())],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    payload = await service.get_for_user(user_id=auth.user_id, business_id=business_id)
    return success(payload)


@businesses_router.patch("/{business_id}", summary="Update business identity fields")
async def update_business(
    business_id: str,
    body: UpdateBusinessRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_business_permission("businesses", "manage"))],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    result = await service.update_for_user(
        user_id=auth.user_id,
        business_id=business_id,
        name=body.name,
        legal_name=body.legal_name,
        tax_number=body.tax_number,
        contact_email=str(body.contact_email) if body.contact_email else None,
        contact_phone=body.contact_phone,
        address=body.address.model_dump() if body.address else None,
        description=body.description,
        website=body.website,
        year_established=body.year_established,
        company_size=body.company_size,
        industry_categories=body.industry_categories,
        business_tags=body.business_tags,
        email_domain=body.email_domain,
        ip_address=client_ip(request),
    )
    return success(result)


@businesses_router.post(
    "/{business_id}/media/{kind}",
    summary="Upload business logo or cover image",
)
async def upload_business_media(
    business_id: str,
    kind: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_business_permission("businesses", "manage"))],
    service: Annotated[BusinessService, Depends(get_business_service)],
    file: Annotated[UploadFile, File(...)],
) -> dict[str, Any]:
    from app.modules.identity.storage import save_business_image

    url = await save_business_image(business_id=business_id, kind=kind, upload=file)
    result = await service.set_business_media(
        user_id=auth.user_id,
        business_id=business_id,
        kind=kind,
        url=url,
        ip_address=client_ip(request),
    )
    return success(result)


@businesses_router.post(
    "/{business_id}/verification/documents/{document_type}",
    summary="Upload one supplier verification document",
)
async def upload_supplier_verification_document(
    business_id: str,
    document_type: str,
    auth: Annotated[AuthContext, Depends(require_business_permission("businesses", "manage"))],
    file: Annotated[UploadFile, File(...)],
) -> dict[str, Any]:
    from app.modules.identity.storage import save_verification_document

    if document_type not in REQUIRED_SUPPLIER_DOCUMENT_TYPES:
        raise BadRequestError("Unknown verification document type")
    original_name = file.filename
    url = await save_verification_document(
        business_id=business_id,
        document_type=document_type,
        upload=file,
    )
    return success(
        {
            "document_type": document_type,
            "file_name": original_name,
            "url": url,
        }
    )


@businesses_router.get(
    "/{business_id}/verification/documents/{document_type}/files/{filename}",
    summary="Download a supplier verification document (staff or company member)",
)
async def download_supplier_verification_document(
    business_id: str,
    document_type: str,
    filename: str,
    auth: Annotated[AuthContext, Depends(require_verification_document_access())],
):
    from fastapi.responses import FileResponse

    from app.modules.identity.repository import SupplierProfileRepository
    from app.modules.identity.storage import (
        media_type_for_verification_file,
        resolve_verification_path,
    )

    path = resolve_verification_path(
        business_id=business_id,
        document_type=document_type,
        filename=filename,
    )
    download_name = filename
    profile = await SupplierProfileRepository().get_by_business(business_id)
    suffix = f"/files/{filename}"
    for row in (profile or {}).get("documents") or []:
        if not isinstance(row, dict):
            continue
        stored = str(row.get("url") or "")
        if stored.endswith(suffix) and row.get("file_name"):
            download_name = str(row["file_name"])
            break
    return FileResponse(
        path,
        filename=download_name,
        media_type=media_type_for_verification_file(path),
        content_disposition_type="inline",
    )


@businesses_router.post(
    "/{business_id}/verification/submit",
    summary="Submit supplier documents for platform review",
)
async def submit_supplier_verification(
    business_id: str,
    body: SubmitSupplierVerificationRequest,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_business_permission("businesses", "manage"))],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    result = await service.submit_supplier_verification(
        user_id=auth.user_id,
        business_id=business_id,
        documents=[row.model_dump() for row in body.documents],
        ip_address=client_ip(request),
    )
    return success(result)


@businesses_router.delete(
    "/{business_id}/verification/documents/{document_type}",
    summary="Withdraw one verification document while review is pending",
)
async def withdraw_supplier_document(
    business_id: str,
    document_type: str,
    request: Request,
    auth: Annotated[AuthContext, Depends(require_business_permission("businesses", "manage"))],
    service: Annotated[BusinessService, Depends(get_business_service)],
) -> dict[str, Any]:
    result = await service.withdraw_supplier_document(
        user_id=auth.user_id,
        business_id=business_id,
        document_type=document_type,
        ip_address=client_ip(request),
    )
    return success(result)
