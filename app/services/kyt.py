from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KYTResult:
    score: int
    level: str
    categories: list[str]
    provider: str = "MOCK_ELLIPTIC"


class MockKYTProvider:
    """Educational stand-in for Elliptic/Chainalysis.

    It demonstrates the API boundary and policy decision, but does not perform
    real blockchain analytics.
    """

    def screen(self, address: str, configured_score: int = 0) -> KYTResult:
        lowered = address.lower()
        score = configured_score
        categories: list[str] = []
        if any(token in lowered for token in ("hack", "mixer", "ransom")):
            score = max(score, 95)
            categories.append("STOLEN_FUNDS_OR_MIXER_EXPOSURE")
        if score >= 80:
            level = "HIGH"
        elif score >= 40:
            level = "MEDIUM"
        else:
            level = "LOW"
        return KYTResult(score=score, level=level, categories=categories)
