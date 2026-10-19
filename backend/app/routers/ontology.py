"""Read-only versioned ontology API (seed JSON; no vendor editor)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_current_user
from app.models import User
from app.ontology_registry import get_ontology, list_ontologies
from app.schemas import OntologyDetailOut, OntologySummaryOut

router = APIRouter(prefix="/api/ontology", tags=["ontology"])


@router.get("", response_model=List[OntologySummaryOut])
def ontology_index(_user: User = Depends(get_current_user)):
    """List registered ontology versions (Admin / Buyer / Contributor)."""
    return [OntologySummaryOut(**row) for row in list_ontologies()]


@router.get("/{ontology_id}", response_model=OntologyDetailOut)
def ontology_detail(
    ontology_id: str,
    version: Optional[str] = Query(None, description="schema_version; default = latest"),
    _user: User = Depends(get_current_user),
):
    try:
        doc = get_ontology(ontology_id, version)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    return OntologyDetailOut(
        ontology_id=str(doc["ontology_id"]),
        schema_version=str(doc["schema_version"]),
        data_type=str(doc["data_type"]),
        title=str(doc.get("title") or ontology_id),
        description=str(doc.get("description") or ""),
        safety=dict(doc.get("safety") or {}),
        required_label_fields=list(doc.get("required_label_fields") or []),
        required_submission_fields=list(doc.get("required_submission_fields") or []),
        fields=dict(doc.get("fields") or {}),
    )
