from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db, get_master_db, MasterBase, ProjectBase
from ..auth import require_internal
from ..diagram_utils import generate_erd_xml, generate_state_diagram_xml
from ..workflow_definitions import DOCUMENT_TRANSITIONS, BOARD_ITEM_TRANSITIONS

# Same treatment as whiteboards.py — internal working tool, gated wholesale.
router = APIRouter(prefix="/api/{slug}/diagrams", tags=["diagrams"], dependencies=[Depends(require_internal)])


def _upsert_whiteboard(db: Session, title: str, xml_content: str) -> models.Whiteboard:
    """Regenerating reuses the whiteboard row with this exact title (created
    the first time) rather than creating a new one each time, so manual
    edits the user makes afterward keep living in a stable, findable place —
    per the spec's "Regenerate ทับของเดิม" requirement."""
    obj = db.query(models.Whiteboard).filter(models.Whiteboard.title == title).first()
    if obj:
        obj.xml_content = xml_content
    else:
        obj = models.Whiteboard(title=title, xml_content=xml_content)
        db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/erd", response_model=schemas.WhiteboardOut)
def generate_erd(
    slug: str,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
    project_name = project.name if project else slug
    xml = generate_erd_xml(
        [("Master DB", MasterBase.metadata), (f"Project DB ({slug})", ProjectBase.metadata)]
    )
    return _upsert_whiteboard(db, f"ERD - {project_name}", xml)


@router.get("/workflow/document-status", response_model=schemas.WhiteboardOut)
def generate_document_status_workflow(slug: str, db: Session = Depends(get_project_db)):
    xml = generate_state_diagram_xml(DOCUMENT_TRANSITIONS, "Document Status Workflow")
    return _upsert_whiteboard(db, "Workflow - Document Status", xml)


@router.get("/workflow/board-item-promote", response_model=schemas.WhiteboardOut)
def generate_board_item_promote_workflow(slug: str, db: Session = Depends(get_project_db)):
    xml = generate_state_diagram_xml(BOARD_ITEM_TRANSITIONS, "Board Item Promote Workflow")
    return _upsert_whiteboard(db, "Workflow - Board Item Promote", xml)
