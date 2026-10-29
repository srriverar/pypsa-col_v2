"""Combustion, attributed electricity, avoided — three accounting views."""

from __future__ import annotations

import pandas as pd

from .catalog import EF_ELEC_T_PER_MWH, FE_KG_PER_TJ, FUELS, GWP_AR5_100, GWP_VERSION

PJ_TO_TJ = 1000.0
PJ_TO_MWH = 1e15 / 3.6e9  # 1 PJ = 277_777.78 MWh


def combustion_from_pj(fuel: str, energy_pj: float) -> dict[str, float]:
    fe = FE_KG_PER_TJ.get(fuel) or {"CO2": 0.0, "CH4": 0.0, "N2O": 0.0}
    tj = energy_pj * PJ_TO_TJ
    out = {g: tj * fe.get(g, 0.0) / 1000.0 for g in ("CO2", "CH4", "N2O")}  # tonnes
    bio = bool((FUELS.get(fuel) or {}).get("biogenic_co2"))
    out["CO2_biogenico_t"] = out["CO2"] if bio else 0.0
    out["CO2_fosil_t"] = 0.0 if bio else out["CO2"]
    out["CO2e_fosil_t"] = (
        out["CO2_fosil_t"]
        + out["CH4"] * GWP_AR5_100["CH4"]
        + out["N2O"] * GWP_AR5_100["N2O"]
    )
    out["gwp_version"] = GWP_VERSION  # type: ignore[assignment]
    return out


def attributed_electricity_t(energy_pj: float, factor: float | None = None) -> float:
    f = EF_ELEC_T_PER_MWH if factor is None else float(factor)
    return float(energy_pj) * PJ_TO_MWH * f


def add_emissions(df: pd.DataFrame) -> pd.DataFrame:
    """df with columns fuel, value (PJ if kind consumo)."""
    recs = []
    for _, row in df.iterrows():
        fuel = str(row["fuel"])
        pj = float(row["value"])
        em = combustion_from_pj(fuel, pj)
        elec = fuel.startswith("Electricidad")
        recs.append(
            {
                **row.to_dict(),
                "co2_fosil_t": 0.0 if elec else em["CO2_fosil_t"],
                "co2_biogenico_t": 0.0 if elec else em["CO2_biogenico_t"],
                "ch4_t": 0.0 if elec else em["CH4"],
                "n2o_t": 0.0 if elec else em["N2O"],
                "co2e_directo_t": 0.0 if elec else em["CO2e_fosil_t"],
                "co2e_elec_atribuido_t": attributed_electricity_t(pj) if elec else 0.0,
            }
        )
    return pd.DataFrame(recs)
