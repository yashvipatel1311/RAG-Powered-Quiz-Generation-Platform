"""
Academix AI — Notice Board Router

In-app notification feed endpoints.
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.dependencies import get_current_user, require_role, CurrentUser
from app.models.notice import NoticeCreate, NoticeResponse, NoticeListResponse, MarkReadRequest
from app.services import notice_service

router = APIRouter()


@router.get("/", response_model=NoticeListResponse)
async def list_notices(
    course_id: Optional[str] = Query(None),
    notice_type: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get the notice feed for the current user."""
    return await notice_service.list_notices(
        user_id=current_user.id,
        role=current_user.role,
        course_id=course_id,
        notice_type=notice_type,
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=NoticeResponse)
async def create_notice(
    data: NoticeCreate,
    current_user: CurrentUser = Depends(require_role("admin", "teacher")),
):
    """Create a new notice (admin/teacher only)."""
    return await notice_service.create_notice(
        posted_by=current_user.id,
        title=data.title,
        body=data.body,
        notice_type=data.notice_type,
        course_id=data.course_id or None,
        target_roles=data.target_roles,
    )


@router.post("/mark-read")
async def mark_as_read(
    data: MarkReadRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Mark notices as read."""
    await notice_service.mark_as_read(current_user.id, data.notice_ids)
    return {"message": "Notices marked as read"}


@router.get("/unread-count")
async def get_unread_count(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get unread notice count (for badge display)."""
    count = await notice_service.get_unread_count(current_user.id, current_user.role)
    return {"unread_count": count}
