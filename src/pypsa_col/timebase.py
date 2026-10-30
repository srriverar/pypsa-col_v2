"""Representative time and inter-epoch demand growth (Motor B / PyPSA-CL style).

The bundled networks ship 24 hourly snapshots (a diurnal shape). Planning
questions need (a) growth from one epoch to the next and (b) a year built from
representative months × day types, with PyPSA ``snapshot_weightings`` so that
Σ P·w ≈ annual MWh.

References: PyPSA snapshot_weightings; Hörsch, Brown et al. PyPSA-Eur;
PyPSA-CL representative years/months/days; XM monthly DemaReal seasonality
(illustrative factors, not an official UPME forecast).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

# UPME-like annual demand growth (%/year) on top of the C1–U3 level scale.
# Order of magnitude of recent SIN growth, differentiated by scenario family.
ANNUAL_GROWTH = {
    "Baja - C1": 0.020,
    "Baja - U1": 0.018,
    "Media - C2": 0.028,
    "Media - U2": 0.030,
    "Alta - C3": 0.038,
    "Alta - U3": 0.042,
}

# Mean monthly energy / mean month, Colombia SIN-like (illustrative).
MONTH_DEMAND = {
    1: 1.03,
    2: 0.97,
    3: 1.00,
    4: 0.99,
    5: 1.00,
    6: 0.98,
    7: 0.99,
    8: 1.01,
    9: 1.02,
    10: 1.03,
    11: 1.04,
    12: 1.06,
}

# Hydro availability vs mean (wet Apr–Jun / Oct–Nov).
MONTH_HYDRO = {
    1: 0.78,
    2: 0.75,
    3: 0.82,
    4: 1.05,
    5: 1.18,
    6: 1.15,
    7: 1.02,
    8: 0.95,
    9: 0.92,
    10: 1.12,
    11: 1.20,
    12: 0.95,
}

MONTH_SOLAR = {
    1: 1.08,
    2: 1.06,
    3: 1.04,
    4: 0.98,
    5: 0.94,
    6: 0.92,
    7: 0.95,
    8: 0.98,
    9: 1.00,
    10: 1.00,
    11: 1.00,
    12: 1.05,
}

MONTH_WIND = {
    1: 1.15,
    2: 1.12,
    3: 1.08,
    4: 0.95,
    5: 0.88,
    6: 0.85,
    7: 0.90,
    8: 0.95,
    9: 1.00,
    10: 1.02,
    11: 1.05,
    12: 1.12,
}

# (name, demand_mult, share_of_month_days) — shares sum to 1.
DAY_TYPES_1 = (("típico", 1.00, 1.00),)
DAY_TYPES_2 = (
    ("laboral", 1.04, 5 / 7),
    ("fin_de_semana", 0.88, 2 / 7),
)
# Lunes–domingo (52 semanas + 1 día extra en domingo).
DAY_TYPES_7 = (
    ("lunes", 1.03, 52 / 365),
    ("martes", 1.05, 52 / 365),
    ("miércoles", 1.05, 52 / 365),
    ("jueves", 1.04, 52 / 365),
    ("viernes", 1.03, 52 / 365),
    ("sábado", 0.90, 52 / 365),
    ("domingo", 0.82, 53 / 365),
)

# Hourly shape (mean = 1) calibrated to typical XM DemaReal / SIN:
# valley 03–05 h, ramp 6–9, plateau, evening peak 18–20 h.
# Saturday later and softer peak; Sunday much lower morning and evening.
def _n(vals: list[float]) -> np.ndarray:
    a = np.asarray(vals, dtype=float)
    return a / float(a.mean() or 1.0)


_SHAPE_WD = _n(
    [0.78, 0.74, 0.71, 0.70, 0.70, 0.74, 0.86, 0.98, 1.06, 1.09, 1.11, 1.12, 1.11, 1.09, 1.08, 1.07, 1.09, 1.16, 1.24, 1.20, 1.10, 0.99, 0.90, 0.83]
)
_SHAPE_FRI = _n(
    [0.80, 0.75, 0.72, 0.71, 0.71, 0.75, 0.86, 0.97, 1.05, 1.08, 1.10, 1.11, 1.10, 1.08, 1.07, 1.07, 1.10, 1.18, 1.22, 1.14, 1.04, 0.96, 0.90, 0.85]
)
_SHAPE_SAT = _n(
    [0.86, 0.81, 0.77, 0.75, 0.74, 0.76, 0.80, 0.86, 0.94, 1.04, 1.10, 1.14, 1.14, 1.10, 1.05, 1.02, 1.02, 1.08, 1.14, 1.12, 1.04, 0.97, 0.91, 0.87]
)
_SHAPE_SUN = _n(
    [0.84, 0.80, 0.76, 0.74, 0.73, 0.73, 0.75, 0.79, 0.85, 0.93, 1.00, 1.06, 1.08, 1.05, 1.00, 0.96, 0.95, 0.99, 1.05, 1.06, 1.00, 0.94, 0.88, 0.84]
)
_DAY_SHAPE = {
    "típico": _SHAPE_WD,
    "laboral": _SHAPE_WD,
    "lunes": _SHAPE_WD * 0.98,  # Monday morning slightly softer
    "martes": _SHAPE_WD,
    "miércoles": _SHAPE_WD,
    "jueves": _SHAPE_WD,
    "viernes": _SHAPE_FRI,
    "sábado": _SHAPE_SAT,
    "fin_de_semana": _SHAPE_SAT,
    "domingo": _SHAPE_SUN,
}


def hour_factor(day_name: str, hour: int) -> float:
    """Diurnal × day-type shape (mean ~1 for a weekday). Distinct lun–dom."""
    sh = _DAY_SHAPE.get(day_name, _SHAPE_WD)
    return float(sh[int(hour) % 24])

BASE_YEAR = 2026
DAYS_IN_MONTH = (0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def growth_rate(demand_key: str) -> float:
    return float(ANNUAL_GROWTH.get(demand_key, 0.028))


def epoch_year(settings: dict) -> int:
    raw = str(settings.get("start_date") or f"{BASE_YEAR}-01-01")[:4]
    try:
        return int(raw)
    except ValueError:
        return BASE_YEAR


def demand_growth_factor(settings: dict) -> float:
    """Compound growth from BASE_YEAR to the epoch start year."""
    g = growth_rate(settings.get("demand_scenario", "Media - C2"))
    y = epoch_year(settings)
    return (1.0 + g) ** max(0, y - BASE_YEAR)


def selected_months(n_months: int) -> list[int]:
    n = int(n_months or 1)
    if n >= 12:
        return list(range(1, 13))
    if n >= 6:
        return [1, 3, 5, 7, 9, 11]
    if n >= 4:
        return [1, 4, 7, 10]
    if n >= 2:
        return [3, 9]
    return [3]


def day_types(n_days: int) -> tuple[tuple[str, float, float], ...]:
    n = int(n_days or 1)
    if n >= 7:
        return DAY_TYPES_7
    if n >= 2:
        return DAY_TYPES_2
    return DAY_TYPES_1


def _base_diurnal(n) -> pd.Series:
    """System MW shape of length 24 from the network's first day."""
    if not hasattr(n, "loads_t") or n.loads_t.p_set.empty:
        return pd.Series(np.ones(24), index=range(24))
    hourly = n.loads_t.p_set.sum(axis=1)
    vals = hourly.to_numpy(dtype=float)
    if len(vals) >= 24:
        day = vals[:24]
    else:
        day = np.resize(vals, 24)
    return pd.Series(day, index=range(24))


def cap_horizon(n, settings: dict) -> tuple[int, int, str]:
    """Keep large AC meshes solvable (STN ~144 buses, OSM ~251).

    Full 6 months × 7 days × 24 h on 251 buses is a multi-million-row LP.
    Cap unless ``full_horizon`` is set. Cloud (/mount/src) is stricter.
    """
    from pathlib import Path

    n_months = max(1, int(settings.get("representative_months") or 1))
    n_days = max(1, int(settings.get("representative_days") or 1))
    n_buses = int(len(getattr(n, "buses", [])))
    if bool(settings.get("full_horizon")):
        return n_months, n_days, ""
    cloud = Path("/mount/src").exists()
    note = ""
    if n_buses >= 200:
        lim_m, lim_d = (1, 2) if cloud else (2, 7)
        if n_months > lim_m or n_days > lim_d:
            note = (
                f"Red grande ({n_buses} barras): horizonte capado a "
                f"{min(n_months, lim_m)} mes(es) × {min(n_days, lim_d)} día(s). "
                "Marque «Horizonte completo» para forzar el original."
            )
        n_months, n_days = min(n_months, lim_m), min(n_days, lim_d)
    elif n_buses >= 80:
        lim_m, lim_d = (2, 7) if cloud else (6, 7)
        if n_months > lim_m or n_days > lim_d:
            note = (
                f"El Modelo STN ({n_buses} barras): horizonte capado a "
                f"{min(n_months, lim_m)} mes(es) × {min(n_days, lim_d)} día(s) "
                "para que HiGHS quepa en RAM. «Horizonte completo» desactiva el tope."
            )
        n_months, n_days = min(n_months, lim_m), min(n_days, lim_d)
    return n_months, n_days, note


def expand_representative_year(n, settings: dict) -> dict:
    """Replace snapshots with representative months × day types; set weightings.

    Call on a freshly loaded network (24 h). Idempotent if already expanded.
    """
    n_months, n_days, cap_note = cap_horizon(n, settings)
    year = epoch_year(settings)
    months = selected_months(n_months)
    types = day_types(n_days)
    climate = settings.get("climate_scenario", "Neutral")
    climate_m = 1.03 if climate == "Niño" else (0.98 if climate == "Niña" else 1.0)

    if hasattr(n, "loads_t") and not n.loads_t.p_set.empty and len(n.snapshots) > 48:
        return {
            "n_snapshots": int(len(n.snapshots)),
            "months": months,
            "day_types": [t[0] for t in types],
            "already_expanded": True,
            "cap_note": cap_note,
        }

    diurnal = _base_diurnal(n)
    mean_d = float(diurnal.mean()) or 1.0
    shape24 = (diurnal / mean_d).to_numpy()

    load0 = n.loads_t.p_set.copy() if hasattr(n, "loads_t") else pd.DataFrame()
    if not load0.empty:
        first = load0.iloc[: min(24, len(load0))].reset_index(drop=True)
        if len(first) < 24:
            first = pd.concat([first] * 24, ignore_index=True).iloc[:24]
        bus_shape = first.div(first.sum(axis=1).replace(0, np.nan), axis=0).fillna(1.0 / max(len(first.columns), 1))
        bus_level = first.mean(axis=0)
    else:
        bus_shape = None
        bus_level = None

    pu0 = None
    if hasattr(n, "generators_t") and "p_max_pu" in n.generators_t and not n.generators_t.p_max_pu.empty:
        pu0 = n.generators_t.p_max_pu.iloc[: min(24, len(n.generators_t.p_max_pu))].reset_index(drop=True)
        if len(pu0) < 24:
            pu0 = pd.concat([pu0] * 24, ignore_index=True).iloc[:24]

    snaps = []
    weights = []
    load_rows = []
    pu_rows = []
    meta_month = []
    meta_day = []
    for m in months:
        dim = DAYS_IN_MONTH[m]
        # if we subsample months, each selected month also stands for neighbours
        month_span = 12 / len(months)
        for name, dmult, share in types:
            n_rep_days = dim * share * month_span
            for h in range(24):
                # Anchor on a Monday of that month so dayofweek matches lun–dom.
                first = pd.Timestamp(year=year, month=m, day=1)
                monday = first + pd.Timedelta(days=(0 - int(first.dayofweek)) % 7)
                ts = monday + pd.Timedelta(
                    days={
                        "típico": 0,
                        "laboral": 0,
                        "fin_de_semana": 5,
                        "lunes": 0,
                        "martes": 1,
                        "miércoles": 2,
                        "jueves": 3,
                        "viernes": 4,
                        "sábado": 5,
                        "domingo": 6,
                    }.get(name, 0),
                    hours=h,
                )
                snaps.append(ts)
                weights.append(max(n_rep_days, 0.01))
                hf = hour_factor(name, h)
                factor = MONTH_DEMAND[m] * dmult * climate_m * hf
                meta_month.append(m)
                meta_day.append(name)
                if bus_level is not None:
                    # MW = mean bus × forma horaria XM-SIN (lun–dom distintas) × mes × clima
                    row = bus_level * factor
                    load_rows.append(row)
                if pu0 is not None:
                    src = pu0.iloc[h].copy()
                    pu_rows.append(src)

    index = pd.DatetimeIndex(snaps, name="snapshot")
    # collision safety
    if index.has_duplicates:
        index = pd.DatetimeIndex(
            [s + pd.Timedelta(minutes=i % 60) for i, s in enumerate(snaps)],
            name="snapshot",
        )
    n.set_snapshots(index)
    w = pd.Series(weights, index=index, dtype=float)
    for col in n.snapshot_weightings.columns:
        n.snapshot_weightings[col] = w

    if load_rows:
        n.loads_t.p_set = pd.DataFrame(load_rows, index=index)

    if pu_rows:
        pu = pd.DataFrame(pu_rows, index=index)
        carriers = n.generators.carrier
        for g in pu.columns.intersection(n.generators.index):
            car = carriers.get(g, "")
            month_of = pd.Series(meta_month, index=index)
            if car in {"Storage Hydro", "Run of River", "Hydro"}:
                pu[g] = pu[g] * month_of.map(MONTH_HYDRO).astype(float)
            elif car == "Solar":
                pu[g] = pu[g] * month_of.map(MONTH_SOLAR).astype(float)
            elif car == "Wind Onshore":
                pu[g] = pu[g] * month_of.map(MONTH_WIND).astype(float)
        n.generators_t.p_max_pu = pu.clip(lower=0.0, upper=1.2)

    return {
        "n_snapshots": int(len(index)),
        "months": months,
        "day_types": [t[0] for t in types],
        "weight_sum_hours": float(w.sum()),
        "already_expanded": False,
        "year": year,
        "cap_note": cap_note,
    }


def monthly_system_mw(n) -> pd.Series:
    """Mean system MW by calendar month (after expansion)."""
    if not hasattr(n, "loads_t") or n.loads_t.p_set.empty:
        return pd.Series(dtype=float)
    s = n.loads_t.p_set.sum(axis=1)
    return s.groupby(s.index.month).mean()


_WEEKDAY_ES = {
    0: "lunes",
    1: "martes",
    2: "miércoles",
    3: "jueves",
    4: "viernes",
    5: "sábado",
    6: "domingo",
}


def daily_profiles_mw(n) -> pd.DataFrame:
    """Mean MW by hour of day × weekday (lunes–domingo) after expansion."""
    if not hasattr(n, "loads_t") or n.loads_t.p_set.empty:
        return pd.DataFrame()
    s = n.loads_t.p_set.sum(axis=1)
    idx = s.index
    if not isinstance(idx, pd.DatetimeIndex):
        return pd.DataFrame()
    tmp = pd.DataFrame({"mw": s.to_numpy(), "h": idx.hour, "d": idx.dayofweek})
    if tmp["d"].nunique() < 2:
        # 1-day expansion: still show 24 h as "típico"
        g = tmp.groupby("h")["mw"].mean()
        return pd.DataFrame({"típico": g})
    piv = tmp.pivot_table(index="h", columns="d", values="mw", aggfunc="mean")
    piv = piv.rename(columns=lambda c: _WEEKDAY_ES.get(int(c), str(c)))
    order = [n for n in ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo") if n in piv.columns]
    return piv[order] if order else piv


def annual_gwh(n) -> float:
    """Σ P_MW × snapshot_weighting (hours) / 1000."""
    if not hasattr(n, "loads_t") or n.loads_t.p_set.empty:
        return 0.0
    p = n.loads_t.p_set.sum(axis=1)
    if "objective" in n.snapshot_weightings.columns:
        w = n.snapshot_weightings["objective"].reindex(p.index).fillna(1.0)
    else:
        w = pd.Series(1.0, index=p.index)
    return float((p * w).sum()) / 1000.0
