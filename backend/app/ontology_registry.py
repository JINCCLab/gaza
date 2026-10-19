"""Load and validate against versioned Phase-0 ontology seed files."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.campaign_types import DATA_TYPE_CV, DATA_TYPE_OSINT, is_cv_campaign, normalize_data_type

ONTOLOGY_DIR = Path(__file__).resolve().parent / "ontology"

# (ontology_id, schema_version) → filename stem convention
_SEED_FILES = (
    "osint_v0.json",
    "cv_v0.json",
)


@lru_cache(maxsize=1)
def _all_ontologies() -> Dict[Tuple[str, str], Dict[str, Any]]:
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for name in _SEED_FILES:
        path = ONTOLOGY_DIR / name
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        oid = str(data["ontology_id"])
        ver = str(data["schema_version"])
        out[(oid, ver)] = data
    return out


def default_for_data_type(data_type: str) -> Dict[str, Any]:
    dt = normalize_data_type(data_type)
    candidates = [d for (_, _), d in _all_ontologies().items() if d.get("data_type") == dt]
    if not candidates:
        raise KeyError(f"No ontology registered for data_type={dt}")
    # Prefer highest semver-ish string sort for v0 (single version per type today)
    candidates.sort(key=lambda d: d.get("schema_version", ""), reverse=True)
    return candidates[0]


def list_ontologies() -> List[Dict[str, Any]]:
    defaults = {}
    for dt in (DATA_TYPE_OSINT, DATA_TYPE_CV):
        try:
            d = default_for_data_type(dt)
            defaults[(d["ontology_id"], d["schema_version"])] = True
        except KeyError:
            pass
    rows = []
    for (oid, ver), data in sorted(_all_ontologies().items(), key=lambda x: (x[0][0], x[0][1])):
        rows.append(
            {
                "ontology_id": oid,
                "schema_version": ver,
                "data_type": data.get("data_type"),
                "title": data.get("title"),
                "description": data.get("description"),
                "is_default": (oid, ver) in defaults,
            }
        )
    return rows


def get_ontology(ontology_id: str, schema_version: Optional[str] = None) -> Dict[str, Any]:
    oid = (ontology_id or "").strip()
    if not oid:
        raise KeyError("ontology_id required")
    registry = _all_ontologies()
    if schema_version:
        key = (oid, schema_version.strip())
        if key not in registry:
            raise KeyError(f"Unknown ontology {oid}@{schema_version}")
        return registry[key]
    # latest for this id
    matches = [d for (i, _), d in registry.items() if i == oid]
    if not matches:
        raise KeyError(f"Unknown ontology_id={oid}")
    matches.sort(key=lambda d: d.get("schema_version", ""), reverse=True)
    return matches[0]


def resolve_pin(
    data_type: str,
    ontology_id: Optional[str] = None,
    schema_version: Optional[str] = None,
) -> Tuple[str, str, Dict[str, Any]]:
    """Resolve campaign pin; returns (ontology_id, schema_version, ontology_doc)."""
    dt = normalize_data_type(data_type)
    if ontology_id or schema_version:
        oid = (ontology_id or dt).strip()
        doc = get_ontology(oid, schema_version)
        if doc.get("data_type") != dt:
            raise ValueError(
                f"Ontology {doc['ontology_id']}@{doc['schema_version']} is for "
                f"{doc.get('data_type')}, not campaign data_type={dt}"
            )
        return str(doc["ontology_id"]), str(doc["schema_version"]), doc
    doc = default_for_data_type(dt)
    return str(doc["ontology_id"]), str(doc["schema_version"]), doc


def ontology_to_requirements(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Build campaign requirements_json defaults from ontology enums."""
    fields = doc.get("fields") or {}
    out: Dict[str, Any] = {
        "ontology_id": doc.get("ontology_id"),
        "schema_version": doc.get("schema_version"),
    }
    et = fields.get("event_type") or {}
    if et.get("values"):
        out["event_types"] = list(et["values"])
    eq = fields.get("equipment_type") or {}
    if eq.get("values"):
        out["equipment_types"] = list(eq["values"])
    loc_g = fields.get("location_granularity") or {}
    if loc_g.get("campaign_default"):
        out["location_granularity"] = loc_g["campaign_default"]
    elif loc_g.get("values"):
        out["location_granularity"] = loc_g["values"][0]
    cat = fields.get("category") or {}
    if cat.get("values"):
        out["categories"] = list(cat["values"])
    safety = doc.get("safety") or {}
    if safety:
        out["safety"] = safety
    if doc.get("data_type") == DATA_TYPE_OSINT:
        out["label_guide_en"] = (
            "Tag public open-source items only. Use public city/region location. "
            "Include source URL from allowlisted hosts. Schema: "
            f"{doc.get('ontology_id')}@{doc.get('schema_version')}."
        )
    if doc.get("data_type") == DATA_TYPE_CV:
        out["annotation_guide_en"] = (
            "Annotate whitelist public scenes only. Schema: "
            f"{doc.get('ontology_id')}@{doc.get('schema_version')}."
        )
        out["bbox_normalized"] = True
        out["media_sources"] = ["upload", "allowlisted_url"]
    return out


def validate_labels_against_ontology(
    doc: Dict[str, Any],
    *,
    labels: Dict[str, Any],
    source_url: str = "",
    storage_key: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """
    Return (ok, error_codes). Failures → reject with schema_policy.
    Does not check allowlist (provenance stage).
    """
    errors: List[str] = []
    labels = labels or {}
    fields = doc.get("fields") or {}

    for key in doc.get("required_label_fields") or []:
        val = labels.get(key)
        if val is None or (isinstance(val, str) and not str(val).strip()):
            errors.append(f"missing_{key}")

    for key in doc.get("required_submission_fields") or []:
        if key == "source_url":
            # CV may use upload instead
            if is_cv_campaign(str(doc.get("data_type") or "")):
                if not (source_url or "").strip() and not storage_key:
                    errors.append("missing_media")
            elif not (source_url or "").strip():
                errors.append("missing_source_url")

    for fname, fdef in fields.items():
        if not isinstance(fdef, dict):
            continue
        # campaign-only fields are not validated on labels
        if fname == "location_granularity":
            continue
        if fname == "source_url":
            continue
        if fname == "bboxes":
            continue
        if fdef.get("optional") and fname not in labels:
            continue
        if fname not in labels:
            continue
        val = labels.get(fname)
        if fdef.get("type") == "enum":
            allowed = set(fdef.get("values") or [])
            if allowed and val not in allowed:
                errors.append(f"{fname}_not_in_enum")
        if fdef.get("type") == "string" and isinstance(val, str):
            mn = fdef.get("min_length")
            mx = fdef.get("max_length")
            if mn is not None and len(val.strip()) < int(mn):
                errors.append(f"{fname}_too_short")
            if mx is not None and len(val) > int(mx):
                errors.append(f"{fname}_too_long")

    return (len(errors) == 0, errors)
