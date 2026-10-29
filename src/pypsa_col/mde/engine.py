"""Run Motor A: PEN LEAP results + optional measures + PyPSA contract."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .emissions import PJ_TO_MWH, add_emissions
from .pen_import import load_pen_results
from .policies import apply_policies


@dataclass
class RunConfig:
    scenario: str = "Actualización"
    start_year: int = 2019
    end_year: int = 2052
    policies: list[dict] = field(default_factory=list)
    elec_factor_t_per_mwh: float | None = None


def slice_consumo(df: pd.DataFrame, cfg: RunConfig) -> pd.DataFrame:
    out = df[(df.kind == "consumo_final_pj") & (df.scenario == cfg.scenario)].copy()
    return out[(out.year >= cfg.start_year) & (out.year <= cfg.end_year)]


def run(cfg: RunConfig | None = None) -> dict:
    cfg = cfg or RunConfig()
    raw = load_pen_results()
    cons = slice_consumo(raw, cfg)
    cons = apply_policies(cons, cfg.policies)
    emis = add_emissions(cons)
    leap_emis = raw[
        (raw.kind == "emisiones_final_mtco2e")
        & (raw.scenario == cfg.scenario)
        & (raw.year >= cfg.start_year)
        & (raw.year <= cfg.end_year)
    ]
    elec = cons[cons.fuel.str.startswith("Electricidad")].copy()
    elec["mwh"] = elec["value"] * PJ_TO_MWH
    return {
        "config": cfg,
        "consumo": cons,
        "emisiones_calculadas": emis,
        "emisiones_leap_oficial": leap_emis,
        "electricidad_mwh": elec,
        "gwp_note": "AR5 100 años. Electricidad atribuida NO se suma al inventario de combustión.",
    }


def national_by_year(cons: pd.DataFrame) -> pd.DataFrame:
    g = cons.groupby("year", as_index=False)["value"].sum()
    g = g.rename(columns={"value": "pj"})
    return g


def pivot_sector_fuel(cons: pd.DataFrame, year: int) -> pd.DataFrame:
    y = cons[cons.year == year]
    return y.pivot_table(index="sector", columns="fuel", values="value", aggfunc="sum").fillna(0.0)
