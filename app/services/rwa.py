from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import RWAAsset
from app.services.audit import append_audit
from app.services.authz import require_client_admin


def issue_rwa(
    db: Session,
    *,
    issuer_client_id: int,
    actor_id: int,
    name: str,
    symbol: str,
    total_units: Decimal,
    reserve_description: str,
) -> dict:
    require_client_admin(db, actor_id, issuer_client_id)
    asset = RWAAsset(
        name=name,
        symbol=symbol.upper(),
        total_units=total_units,
        reserve_description=reserve_description,
        issuer_client_id=issuer_client_id,
    )
    db.add(asset)
    db.flush()
    append_audit(
        db,
        actor_id=actor_id,
        action="RWA_ISSUED",
        entity_type="RWA_ASSET",
        entity_id=asset.id,
        payload={
            "name": asset.name,
            "symbol": asset.symbol,
            "units": str(asset.total_units),
            "reserve": asset.reserve_description,
        },
    )
    db.commit()
    return {
        "id": asset.id,
        "name": asset.name,
        "symbol": asset.symbol,
        "total_units": str(asset.total_units),
        "status": asset.status,
        "next_step": f"Deploy the testnet contract with POST /rwa/{asset.id}/onchain/deploy.",
    }
