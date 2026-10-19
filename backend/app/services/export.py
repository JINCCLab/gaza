import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import AuditLog, Campaign, Dataset, Submission
from app.services import storage as object_storage


def build_dataset_export(
    db: Session,
    *,
    campaign: Campaign,
    actor_id: Optional[int] = None,
) -> Dataset:
    accepted = (
        db.query(Submission)
        .filter(
            Submission.campaign_id == campaign.id,
            Submission.verification_status == "accepted",
        )
        .order_by(Submission.id.asc())
        .all()
    )

    existing = (
        db.query(Dataset)
        .filter(Dataset.campaign_id == campaign.id)
        .order_by(Dataset.version.desc())
        .first()
    )
    version = (existing.version + 1) if existing else 1

    items = []
    for s in accepted:
        item = {
            "submission_id": s.id,
            "source_url": s.source_url,
            "storage_key": s.storage_key,
            "labels": s.labels_json,
            "annotation": s.labels_json if (s.metadata_json or {}).get("template") == "cv_media" else None,
            "metadata": s.metadata_json,
            "file_hash": s.file_hash,
            "quality_score": s.quality_score,
            "synthetic_score": s.synthetic_score,
            "final_reward": s.final_reward,
            "accepted_at": s.created_at.isoformat() + "Z",
            "data_type": campaign.data_type,
            "data_class": campaign.data_class,
        }
        items.append(item)

    filename = f"campaign_{campaign.id}_v{version}.jsonl"
    logical_key = f"exports/{filename}"
    body = ("\n".join(json.dumps(item, ensure_ascii=False) for item in items) + ("\n" if items else "")).encode(
        "utf-8"
    )
    stored_key = object_storage.put_bytes(
        logical_key,
        body,
        kind="exports",
        content_type="application/x-ndjson",
    )

    manifest = {
        "campaign_id": campaign.id,
        "campaign_title": campaign.title,
        "data_type": campaign.data_type,
        "data_class": campaign.data_class,
        "synthetic_allowed": campaign.synthetic_allowed,
        "version": version,
        "item_count": len(items),
        "format": "jsonl",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "filename": filename,
        "storage_key": stored_key,
        "storage_backend": object_storage.resolved_storage_backend(),
    }
    manifest_key = f"exports/campaign_{campaign.id}_v{version}_manifest.json"
    object_storage.put_bytes(
        manifest_key,
        json.dumps(manifest, indent=2).encode("utf-8"),
        kind="exports",
        content_type="application/json",
    )

    dataset = Dataset(
        campaign_id=campaign.id,
        organization_id=campaign.organization_id,
        version=version,
        item_count=len(items),
        export_storage_key=stored_key,
        manifest_json=manifest,
    )
    db.add(dataset)
    db.add(
        AuditLog(
            actor_id=actor_id,
            action="dataset_export",
            entity_type="dataset",
            entity_id=None,
            detail_json={"campaign_id": campaign.id, "version": version, "item_count": len(items)},
        )
    )
    db.flush()
    db.add(
        AuditLog(
            actor_id=actor_id,
            action="dataset_export",
            entity_type="dataset",
            entity_id=dataset.id,
            detail_json={
                "campaign_id": campaign.id,
                "version": version,
                "storage_key": stored_key,
                "storage_backend": object_storage.resolved_storage_backend(),
            },
        )
    )
    return dataset
