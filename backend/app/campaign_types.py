"""Phase-0 campaign template types (dual wedge — same platform)."""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Tuple

# Canonical data_type values (aliases accepted on create).
DATA_TYPE_OSINT = "osint_label"
DATA_TYPE_CV = "cv_media"

OSINT_ALIASES = frozenset({"osint_label", "osint_labels"})
CV_ALIASES = frozenset({"cv_media", "cv"})

DATA_CLASS_OSINT = "structured_osint"
DATA_CLASS_CV = "public_scene_cv"

# CV scene categories — public parade / museum / official promo only (no conflict-zone field).
CV_DEFAULT_CATEGORIES = (
    "parade_public",
    "museum_exhibit",
    "official_promo",
    "public_airshow",
    "open_training_viewing",
)

ALLOWED_MEDIA_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".mp4"})


def normalize_data_type(raw: str) -> str:
    v = (raw or "").strip().lower()
    if v in OSINT_ALIASES:
        return DATA_TYPE_OSINT
    if v in CV_ALIASES:
        return DATA_TYPE_CV
    raise ValueError(f"Unsupported data_type={raw!r}; use osint_label|cv_media")


def is_cv_campaign(data_type: str) -> bool:
    try:
        return normalize_data_type(data_type) == DATA_TYPE_CV
    except ValueError:
        return False


def default_requirements(data_type: str) -> Dict[str, Any]:
    """Defaults from versioned ontology seed (falls back to hardcoded if registry missing)."""
    try:
        from app.ontology_registry import default_for_data_type, ontology_to_requirements

        return ontology_to_requirements(default_for_data_type(data_type))
    except Exception:  # noqa: BLE001 — keep create path resilient
        if is_cv_campaign(data_type):
            return {
                "categories": list(CV_DEFAULT_CATEGORIES),
                "annotation_guide_en": (
                    "Annotate whitelist public scenes only (parade, museum, official promo, "
                    "public airshow, open training viewing). Provide category, caption, and "
                    "optional normalized bboxes (x,y,w,h in 0–1). No conflict-zone field collection. "
                    "synthetic_allowed defaults false."
                ),
                "bbox_normalized": True,
                "media_sources": ["upload", "allowlisted_url"],
            }
        return {
            "event_types": [
                "military_exercise",
                "equipment_display",
                "official_briefing",
                "port_call_public",
                "airshow_public",
            ],
            "location_granularity": "public_city_region",
            "equipment_types": ["aircraft", "naval", "ground", "missile_system_public", "unknown"],
            "label_guide_en": (
                "Tag public open-source items only. Use public city/region location. "
                "Include source URL from allowlisted hosts."
            ),
        }


def default_data_class(data_type: str) -> str:
    return DATA_CLASS_CV if is_cv_campaign(data_type) else DATA_CLASS_OSINT


def allowed_cv_categories(requirements: Dict[str, Any]) -> FrozenSet[str]:
    cats = requirements.get("categories") or list(CV_DEFAULT_CATEGORIES)
    return frozenset(str(c) for c in cats)


def validate_campaign_pair(data_type: str, data_class: str) -> Tuple[str, str]:
    dt = normalize_data_type(data_type)
    dc = (data_class or "").strip() or default_data_class(dt)
    if dt == DATA_TYPE_OSINT and dc not in (DATA_CLASS_OSINT, "structured_osint"):
        # allow legacy; coerce unknown to default
        dc = DATA_CLASS_OSINT
    if dt == DATA_TYPE_CV and dc not in (DATA_CLASS_CV, "cv_annotation", "public_scene_annotation"):
        dc = DATA_CLASS_CV
    if dt == DATA_TYPE_CV:
        dc = DATA_CLASS_CV
    else:
        dc = DATA_CLASS_OSINT
    return dt, dc
