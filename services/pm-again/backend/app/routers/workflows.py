from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..workflow_definitions import DOCUMENT_TRANSITIONS, BOARD_ITEM_TRANSITIONS

router = APIRouter(prefix="/api/workflows", tags=["workflows"], dependencies=[Depends(get_current_user)])


@router.get("/document-status")
def get_document_status_transitions() -> dict[str, list[str]]:
    return DOCUMENT_TRANSITIONS


@router.get("/board-item-promote")
def get_board_item_promote_transitions() -> dict[str, list[str]]:
    return BOARD_ITEM_TRANSITIONS
