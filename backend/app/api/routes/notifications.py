from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.notifications import NotificationOut, NotificationsResponse, UnreadCountResponse
from app.schemas.registration import ApiErrorResponse
from app.services.notifications import (
    MAX_BIGINT,
    count_unread,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

UNAUTHENTICATED = {401: {"model": ApiErrorResponse, "description": "Sessão inválida"}}


@router.get(
    "",
    response_model=NotificationsResponse,
    responses={400: {"model": ApiErrorResponse}, **UNAUTHENTICATED},
)
def notifications(
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationsResponse:
    data = list_notifications(db, user, limit, cursor)
    return NotificationsResponse(
        items=[NotificationOut.model_validate(item) for item in data["items"]],
        next_cursor=data["next_cursor"],
        total=data["total"],
    )


@router.get("/unread-count", response_model=UnreadCountResponse, responses=UNAUTHENTICATED)
def unread_count(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> UnreadCountResponse:
    return UnreadCountResponse(count=count_unread(db, user))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT, responses=UNAUTHENTICATED)
def read_all_notifications(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Response:
    mark_all_notifications_read(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **UNAUTHENTICATED,
        403: {"model": ApiErrorResponse, "description": "O aviso é de outro usuário"},
        404: {"model": ApiErrorResponse, "description": "Aviso não encontrado"},
    },
)
def read_notification(
    notification_id: int = Path(ge=1, le=MAX_BIGINT),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    mark_notification_read(db, user, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
