"""Policy measures applied in a documented order (LEAP-style effects)."""

from __future__ import annotations

import pandas as pd

# Application order (explicit):
# 1 activity  2 modal  3 stock  4 fuel substitution  5 efficiency  6 energy
POLICY_ORDER = ("activity", "modal", "stock", "substitution", "efficiency")


def apply_policies(consumo: pd.DataFrame, policies: list[dict] | None) -> pd.DataFrame:
    """Scale PEN energy after the official LEAP path.

    Each policy: {id, type, sector?, fuel?, start, end, factor}
    factor is multiplicative on matching rows from start_year onward
    (linear ramp from 1 to factor between start and end).
    """
    if not policies:
        return consumo
    out = consumo.copy()
    out["policy_factor"] = 1.0
    for p in sorted(policies, key=lambda x: POLICY_ORDER.index(x.get("type", "efficiency")) if x.get("type") in POLICY_ORDER else 99):
        start = int(p.get("start", 2024))
        end = int(p.get("end", 2035))
        target = float(p.get("factor", 1.0))
        sector = p.get("sector")
        fuel = p.get("fuel")
        mask = pd.Series(True, index=out.index)
        if sector:
            mask &= out.sector == sector
        if fuel:
            mask &= out.fuel == fuel
        years = out.year.astype(int)
        ramp = (years - start) / max(end - start, 1)
        ramp = ramp.clip(lower=0.0, upper=1.0)
        fac = 1.0 + ramp * (target - 1.0)
        fac = fac.where(years >= start, 1.0)
        out.loc[mask, "policy_factor"] = out.loc[mask, "policy_factor"] * fac[mask]
    out["value"] = out["value"] * out["policy_factor"]
    return out


DEFAULT_POLICIES = [
    {
        "id": "buses_electricos",
        "type": "substitution",
        "label": "Electrificación buses (ilustrativa)",
        "sector": "transporte",
        "fuel": "Diesel",
        "start": 2026,
        "end": 2040,
        "factor": 0.90,
        "note": "Reduce diésel 10% al 2040. La electricidad extra se modela aparte.",
    },
    {
        "id": "coccion_limpia",
        "type": "substitution",
        "label": "Cocción limpia rural (leña → GLP/electricidad)",
        "sector": "residencial",
        "fuel": "Leña",
        "start": 2026,
        "end": 2040,
        "factor": 0.70,
        "note": "Servicio de cocción no se supone constante automáticamente.",
    },
    {
        "id": "eficiencia_industria",
        "type": "efficiency",
        "label": "Eficiencia calor industrial",
        "sector": "industria",
        "start": 2026,
        "end": 2035,
        "factor": 0.92,
        "note": "−8% energía final industrial al 2035 (todas las ramas).",
    },
]
