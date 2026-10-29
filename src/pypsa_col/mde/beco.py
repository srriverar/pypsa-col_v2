"""Reconcile Motor A / PEN LEAP against BECO published totals."""

from __future__ import annotations

import pandas as pd

from .catalog import BECO_2023_PJ, BECO_2023_TOTAL_PJ, BECO_NOTE


def reconcile(consumo: pd.DataFrame, year: int = 2023) -> pd.DataFrame:
    y = consumo[consumo.year == year]
    model = y.groupby("sector")["value"].sum()
    rows = []
    for sector, beco in BECO_2023_PJ.items():
        m = float(model.get(sector, 0.0))
        rows.append(
            {
                "sector": sector,
                "year": year,
                "BECO_pj": beco,
                "modelo_pj": m,
                "delta_pj": m - beco,
                "delta_pct": 100.0 * (m - beco) / beco if beco else None,
                "estado_BECO": "oficial_agregado" if sector in {"transporte", "industria", "residencial"} else "reconstruido_resto",
                "nota": BECO_NOTE if sector not in {"transporte", "industria", "residencial"} else "UPME BECO 2023 (F-DP-029)",
            }
        )
    tot_m = float(model.sum())
    rows.append(
        {
            "sector": "TOTAL",
            "year": year,
            "BECO_pj": BECO_2023_TOTAL_PJ,
            "modelo_pj": tot_m,
            "delta_pj": tot_m - BECO_2023_TOTAL_PJ,
            "delta_pct": 100.0 * (tot_m - BECO_2023_TOTAL_PJ) / BECO_2023_TOTAL_PJ,
            "estado_BECO": "oficial",
            "nota": "No mezclar consumo final con transformación / pérdidas / búnker.",
        }
    )
    return pd.DataFrame(rows)
