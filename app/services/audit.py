from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog


def append_audit(
    db: Session,
    *,
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | int,
    payload: dict[str, Any],
) -> AuditLog:
    previous = db.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))
    prev_hash = previous.entry_hash if previous else "0" * 64
    canonical_payload = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    material = f"{prev_hash}|{actor_id}|{action}|{entity_type}|{entity_id}|{canonical_payload}"
    entry_hash = hashlib.sha256(material.encode()).hexdigest()
    row = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        payload_json=canonical_payload,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    db.add(row)
    db.flush()
    return row
