"""Annual MWh → hourly MW for PyPSA (Σ w_h = 1)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .emissions import PJ_TO_MWH

# Weekday × hour weights typical SIN (illustrative, not XM official).
# Rows: lun..dom, cols: 24 h. Each day sums to 1; then days weighted.
_WEEKDAY = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_DAY_W = np.array([1.03, 1.05, 1.05, 1.04, 1.03, 0.90, 0.82], dtype=float)
_DAY_W = _DAY_W / _DAY_W.sum() * 7  # keep mean 1 when combined with 52/53 later

_HOUR = np.array(
    [
        0.72, 0.68, 0.66, 0.65, 0.66, 0.74, 0.88, 1.05, 1.12, 1.10, 1.08, 1.10,
        1.12, 1.10, 1.08, 1.07, 1.10, 1.18, 1.22, 1.20, 1.12, 1.00, 0.88, 0.78,
    ],
    dtype=float,
)
_HOUR = _HOUR / _HOUR.sum()


def weekday_hour_weights() -> pd.DataFrame:
    sat = _HOUR * np.array([0.95] * 8 + [1.05] * 10 + [0.90] * 6)
    sun = _HOUR * np.array([0.90] * 10 + [1.00] * 8 + [0.85] * 6)
    sat = sat / sat.sum()
    sun = sun / sun.sum()
    data = {}
    for i, name in enumerate(_WEEKDAY):
        if name == "sábado":
            h = sat
        elif name == "domingo":
            h = sun
        else:
            h = _HOUR
        data[name] = h
    return pd.DataFrame(data)


def annual_pj_to_hourly_mw(energy_pj: float, year: int = 2026) -> pd.Series:
    """Uniform 8760 h if needed; here 7×24 representative, weights restore year."""
    mwh = float(energy_pj) * PJ_TO_MWH
    wh = weekday_hour_weights()
    shares = {
        "lunes": 52 / 365,
        "martes": 52 / 365,
        "miércoles": 52 / 365,
        "jueves": 52 / 365,
        "viernes": 52 / 365,
        "sábado": 52 / 365,
        "domingo": 53 / 365,
    }
    idx = []
    mw = []
    for d, share in shares.items():
        for h in range(24):
            e_h = mwh * share * float(wh.loc[h, d])
            idx.append(pd.Timestamp(year=year, month=3, day=min(7, 1 + _WEEKDAY.index(d)), hour=h))
            mw.append(e_h)  # MWh in that representative hour *before* weighting
    s = pd.Series(mw, index=pd.DatetimeIndex(idx, name="snapshot"), name="MWh_rep")
    return s


def pypsa_contract(elec: pd.DataFrame, year: int) -> pd.DataFrame:
    y = elec[elec.year == year]
    total_pj = float(y["value"].sum()) if not y.empty else 0.0
    hourly = annual_pj_to_hourly_mw(total_pj, year)
    out = hourly.reset_index()
    out["scenario"] = y["scenario"].iloc[0] if len(y) else None
    out["year"] = year
    out["sector"] = "all_electricity"
    out["energy_carrier"] = "Electricidad_SIN"
    out["annual_mwh"] = total_pj * PJ_TO_MWH
    out["profile_id"] = "weekday_7x24_sin_ilustrativo"
    return out
