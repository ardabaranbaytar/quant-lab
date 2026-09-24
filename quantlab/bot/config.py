"""Bot configuration (JSON-serialisable so it can live in the database)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass
class BotConfig:
    groups: dict[str, str]                  # ticker -> group (e.g. GICS sub-industry)
    companies: dict[str, str] | None = None  # ticker -> issuer, excludes share classes
    capital: float = 100_000.0
    cost_rate: float = 0.001                # cost per unit of traded notional
    formation_days: int = 756
    reselect_every: int = 63                # trading days between pair re-selections
    top_k: int = 20
    max_pvalue: float = 0.05
    half_life_range: tuple[float, float] = (5, 60)
    max_pairs_per_stock: int = 2
    entry_z: float = 2.0
    exit_z: float = 0.0
    stop_z: float | None = None
    break_monitor: bool = True
    monitor_thresholds: dict[str, float] | None = None  # None -> DEFAULT_THRESHOLDS
    break_votes: int = 3
    min_order_value: float = 1.0            # skip orders smaller than this ($)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["half_life_range"] = list(self.half_life_range)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BotConfig:
        known = {f.name for f in fields(cls)}
        kw = {k: v for k, v in d.items() if k in known}
        if "half_life_range" in kw:
            lo, hi = kw["half_life_range"]
            kw["half_life_range"] = (float(lo), float(hi))
        return cls(**kw)
