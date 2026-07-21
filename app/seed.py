from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models import Asset, Client, ClientBalance, User, Wallet
from app.services.audit import append_audit

ASSET_SEED = [
    ("BTC", "Bitcoin", 8, 3),
    ("ETH", "Ethereum", 18, 12),
    ("SOL", "Solana", 9, 1),
    ("AVAX", "Avalanche C-Chain", 18, 12),
    ("XRP", "XRP Ledger", 6, 1),
    ("POL", "Polygon PoS", 18, 128),
]


def reset_and_seed(db: Session) -> dict:
    db.close()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        client = Client(name="ABC Digital Asset Fund")
        session.add(client)
        session.flush()
        users = [
            User(name="CFO Root", role="ROOT", scope="CLIENT", client_id=client.id),
            User(name="Treasury Admin", role="ADMIN", scope="CLIENT", client_id=client.id),
            User(name="Treasury Operator", role="OPERATOR", scope="CLIENT", client_id=client.id),
            User(name="Internal Auditor", role="VIEWER", scope="CLIENT", client_id=client.id),
            User(name="Custody Admin One", role="BACKOFFICE_ADMIN", scope="BACKOFFICE"),
            User(name="Custody Admin Two", role="BACKOFFICE_ADMIN", scope="BACKOFFICE"),
        ]
        session.add_all(users)
        assets: dict[str, Asset] = {}
        for symbol, network, decimals, confirmations in ASSET_SEED:
            asset = Asset(
                symbol=symbol,
                network=network,
                decimals=decimals,
                confirmations_required=confirmations,
            )
            session.add(asset)
            session.flush()
            assets[symbol] = asset
            session.add_all(
                [
                    Wallet(client_id=client.id, asset_id=asset.id, kind="DEPOSIT", address=f"{symbol.lower()}-deposit-abc", label=f"ABC {symbol} Deposit", status="ACTIVE"),
                    Wallet(asset_id=asset.id, kind="OMNIBUS", address=f"{symbol.lower()}-omnibus", label=f"{symbol} Omnibus", status="ACTIVE"),
                    Wallet(asset_id=asset.id, kind="HOT", address=f"{symbol.lower()}-hot", label=f"{symbol} Hot", status="ACTIVE"),
                    Wallet(asset_id=asset.id, kind="WARM", address=f"{symbol.lower()}-warm", label=f"{symbol} Warm", status="ACTIVE"),
                    Wallet(asset_id=asset.id, kind="COLD", address=f"{symbol.lower()}-cold", label=f"{symbol} Cold", status="ACTIVE"),
                ]
            )
        session.flush()
        btc = assets["BTC"]
        eth = assets["ETH"]
        session.add_all(
            [
                ClientBalance(client_id=client.id, asset_id=btc.id, available=Decimal("100")),
                ClientBalance(client_id=client.id, asset_id=eth.id, available=Decimal("1000")),
            ]
        )
        for symbol, values in {
            "BTC": {"HOT": "5", "WARM": "15", "COLD": "80"},
            "ETH": {"HOT": "50", "WARM": "150", "COLD": "800"},
        }.items():
            asset = assets[symbol]
            for kind, amount in values.items():
                wallet = session.scalar(select(Wallet).where(Wallet.asset_id == asset.id, Wallet.kind == kind))
                wallet.balance = Decimal(amount)
        exchange_wallet = Wallet(
            client_id=client.id,
            asset_id=btc.id,
            kind="EXTERNAL",
            address="bc1q-exchange-a-abc-fund",
            label="ABC Fund at Licensed Exchange A",
            status="WHITELISTED",
            risk_score=12,
        )
        session.add(exchange_wallet)
        session.flush()
        append_audit(
            session,
            actor_id=None,
            action="DEMO_SEEDED",
            entity_type="SYSTEM",
            entity_id="1",
            payload={"client": client.name},
        )
        session.commit()
        return {
            "client_id": client.id,
            "root_id": users[0].id,
            "client_admin_id": users[1].id,
            "operator_id": users[2].id,
            "viewer_id": users[3].id,
            "backoffice_admin_1_id": users[4].id,
            "backoffice_admin_2_id": users[5].id,
            "exchange_btc_wallet_id": exchange_wallet.id,
        }
