from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SignedPayload:
    signature: str
    participating_nodes: list[str]
    threshold: int
    algorithm: str = "DEMO-HMAC-SHA256-NOT-REAL-MPC"


class MockMPCSigner:
    """A safe architectural simulation, not an MPC cryptographic implementation.

    Production must replace this adapter with GK8/Galaxy APIs or a certified
    MPC/HSM provider. It only demonstrates threshold participation and the
    signing-provider boundary.
    """

    nodes = ("mpc-node-a", "mpc-node-b", "recovery-node-c")
    threshold = 2

    def sign(self, payload: str, participating_nodes: list[str]) -> SignedPayload:
        unique = sorted(set(participating_nodes))
        if len(unique) < self.threshold:
            raise ValueError("At least two unique MPC participants are required")
        if not set(unique).issubset(set(self.nodes)):
            raise ValueError("Unknown MPC participant")
        secret = os.getenv("DEMO_SIGNING_SECRET", "local-demo-only").encode()
        signature = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
        return SignedPayload(signature=signature, participating_nodes=unique, threshold=self.threshold)
