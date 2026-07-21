from __future__ import annotations


def build_travel_rule_message(*, client_name: str, destination_label: str, asset: str, amount: str) -> dict:
    return {
        "originator": {"name": client_name, "vasp": "IDGX Custody Demo"},
        "beneficiary": {"name": client_name, "account": destination_label},
        "asset": asset,
        "amount": amount,
        "purpose": "CLIENT_OWN_ACCOUNT_TRANSFER",
        "status": "READY_TO_SEND",
    }
