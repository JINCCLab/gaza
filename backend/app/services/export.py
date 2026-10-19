import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuditLog, Campaign, Dataset, Submission


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
        items.append(
            {
                "submission_id": s.id,
                "source_url": s.source_url,
                "labels": s.labels_json,
                "metadata": s.metadata_json,
                "file_hash": s.file_hash,
                "quality_score": s.quality_score,
                "final_reward": s.final_reward,
                "accepted_at": s.created_at.isoformat() + "Z",
            }
        )

    export_dir = Path(settings.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = f"campaign_{campaign.id}_v{version}.jsonl"
    path = export_dir / filename

    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    manifest = {
        "campaign_id": campaign.id,
        "campaign_title": campaign.title,
        "data_type": campaign.data_type,
        "data_class": campaign.data_class,
        "version": version,
        "item_count": len(items),
        "format": "jsonl",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "filename": filename,
    }
    manifest_path = export_dir / f"campaign_{campaign.id}_v{version}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    dataset = Dataset(
        campaign_id=campaign.id,
        organization_id=campaign.organization_id,
        version=version,
        item_count=len(items),
        export_storage_key=str(path),
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
            detail_json={"campaign_id": campaign.id, "version": version, "path": str(path)},
        )
    )
    return dataset
