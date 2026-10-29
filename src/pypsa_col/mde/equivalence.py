"""LEAP → Motor A mapping and comparison against the official anexo."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from .methods import (
    activity_times_intensity,
    kwh_from_vkt,
    liters_from_vkt,
    sequential_measures,
    stock_use_intensity,
    useful_to_final,
)
from .package import data_root

# Official gold cells (anexo, data_only, not recalculated).
GOLD = [
    {
        "id": "gasolina_trans_2030_A",
        "hoja": "Consumo Final A",
        "celda": "I23",
        "escenario": "Actualización",
        "bloque": "Sector Transporte (PJ-año)",
        "energetico": "Gasolina",
        "año": 2030,
        "esperado": 372.7692759648167,
        "unidad": "PJ-año",
        "nota": "Resultado histórico del anexo, no un pronóstico vigente.",
    },
    {
        "id": "diesel_trans_2030_A",
        "hoja": "Consumo Final A",
        "celda": "J23",
        "escenario": "Actualización",
        "bloque": "Sector Transporte (PJ-año)",
        "energetico": "Diesel",
        "año": 2030,
        "esperado": 280.9960516564333,
        "unidad": "PJ-año",
        "nota": "Misma hoja/año que gasolina.",
    },
    {
        "id": "gasolina_emi_2030_A",
        "hoja": "Emisiones Consumo Final A",
        "celda": "I23",
        "escenario": "Actualización",
        "bloque": "Sector Transporte (Mt CO2eq-año)",
        "energetico": "Gasolina",
        "año": 2030,
        "esperado": 26.35848190858241,
        "unidad": "Mt CO2eq-año",
        "nota": "CO2eq del anexo; no revela el GWP interno.",
    },
    {
        "id": "diesel_emi_2030_A",
        "hoja": "Emisiones Consumo Final A",
        "celda": "J23",
        "escenario": "Actualización",
        "bloque": "Sector Transporte (Mt CO2eq-año)",
        "energetico": "Diesel",
        "año": 2030,
        "esperado": 20.91980979353673,
        "unidad": "Mt CO2eq-año",
        "nota": "Pareja diésel de la celda anterior.",
    },
]

MATRIX = [
    {
        "leap": "Rama sectorial (árbol)",
        "motor_a": "branch_id (tree.py)",
        "tipo": "correspondencia agregada",
        "metodo": "catálogo",
        "estado": "homologado a 6 bloques del anexo; IDs internos .leap no extraídos (AES)",
    },
    {
        "leap": "Activity Level",
        "motor_a": "activity",
        "tipo": "variable",
        "metodo": "A o C según unidad",
        "estado": "función equivalente implementada; valor LEAP no extraído",
    },
    {
        "leap": "Final Energy Intensity",
        "motor_a": "intensity_final",
        "tipo": "variable",
        "metodo": "A: E = A × I",
        "estado": "función test_method_a; I implícita = E_anexo / A si hay A",
    },
    {
        "leap": "Useful Energy Intensity",
        "motor_a": "intensity_useful",
        "tipo": "variable",
        "metodo": "B: U = A × I_útil; E = U / η",
        "estado": "función test_method_b; η>1 permitida (COP)",
    },
    {
        "leap": "Fuel Share",
        "motor_a": "share_type=energy_fuel",
        "tipo": "participación",
        "metodo": "no confundir con q de servicio",
        "estado": "documentado; shares del anexo = energía final, no hogares",
    },
    {
        "leap": "Stock / vehículo",
        "motor_a": "stock_cohort",
        "tipo": "stock",
        "metodo": "C: E = N × km × I",
        "estado": "litros_from_vkt y kwh_from_vkt con prueba buses 8 GWh",
    },
    {
        "leap": "Environmental Loading",
        "motor_a": "emission_factor",
        "tipo": "factor",
        "metodo": "FE kg/TJ × PJ; CO2e GWP AR5",
        "estado": "FE implícito = Mt_anexo / PJ_anexo (auditoría, no FECOC oficial)",
    },
    {
        "leap": "Scenario + herencia",
        "motor_a": "scenario_id + parent",
        "tipo": "escenario",
        "metodo": "6 escenarios del índice PEN",
        "estado": "nombres del anexo; herencia interna LEAP no leída",
    },
    {
        "leap": "Expression (Interp, Growth…)",
        "motor_a": "expressions.eval_expr",
        "tipo": "expresión segura",
        "metodo": "JSON const/reference/multiply/grow/interpolate — sin eval()",
        "estado": "motor listo; expresiones del .leap no clonadas",
    },
    {
        "leap": "Saturation vs Share",
        "motor_a": "share_type",
        "tipo": "regla LEAP",
        "metodo": "saturación no suma 100 %",
        "estado": "regla de interfaz documentada",
    },
    {
        "leap": "Demand → resultados Consumo Final",
        "motor_a": "resultados_PEN CSV / engine.run",
        "tipo": "salida",
        "metodo": "lectura celda a celda",
        "estado": "comparación gold I23/J23 al bit",
    },
    {
        "leap": "NDC: IPPU / AFOLU / residuos",
        "motor_a": "(fuera de v1)",
        "tipo": "alcance",
        "metodo": "—",
        "estado": "modelo distinto; no fusionar con PEN",
    },
]


@lru_cache(maxsize=1)
def load_celdas() -> pd.DataFrame:
    p = data_root() / "resultados_PEN_2022_2052.csv"
    return pd.read_csv(p)


def lookup(hoja: str, celda: str) -> float:
    df = load_celdas()
    hit = df[(df.hoja == hoja) & (df.celda == celda)]
    if hit.empty:
        raise KeyError(f"{hoja}!{celda}")
    return float(hit.valor.iloc[0])


def compare_gold(tol: float = 1e-9) -> pd.DataFrame:
    rows = []
    for g in GOLD:
        got = lookup(g["hoja"], g["celda"])
        rows.append(
            {
                **{k: g[k] for k in ("id", "hoja", "celda", "energetico", "año", "unidad", "nota")},
                "esperado_anexo": g["esperado"],
                "leido_csv": got,
                "delta": got - g["esperado"],
                "ok": abs(got - g["esperado"]) <= tol,
            }
        )
    return pd.DataFrame(rows)


def implied_ef_t_per_tj(energy_pj: float, mtco2e: float) -> float:
    """Mt CO2e / PJ  →  t / TJ  (= kg/GJ). 1 PJ = 1000 TJ."""
    if energy_pj == 0:
        return float("nan")
    tonnes = mtco2e * 1e6
    tj = energy_pj * 1000.0
    return tonnes / tj


def function_suite() -> pd.DataFrame:
    checks = [
        ("LEAP Activity×Intensity", "A: 100×2", activity_times_intensity(100, 2), 200.0),
        ("LEAP Useful/Efficiency", "B: 100/0.5", useful_to_final(100, 0.5), 200.0),
        ("LEAP Stock", "C: 100×10000×0.1", stock_use_intensity(100, 10_000, 0.1), 100_000.0),
        ("Transporte diésel", "100 buses × 60e3 km × 0.40 L/km", liters_from_vkt(100, 60_000, 0.40), 2_400_000.0),
        ("Transporte eléctrico", "red 1.2 kWh/km / 0.9", kwh_from_vkt(100, 60_000, 1.20, 0.90), 8_000_000.0),
        ("Interacción medidas", "0.90 then 0.80", sequential_measures(100, [0.9, 0.8]), 72.0),
        ("Anexo I23 gasolina 2030", "Consumo Final A", lookup("Consumo Final A", "I23"), 372.7692759648167),
        ("Anexo J23 diésel 2030", "Consumo Final A", lookup("Consumo Final A", "J23"), 280.9960516564333),
        ("Anexo I23 GEI gasolina", "Emisiones A", lookup("Emisiones Consumo Final A", "I23"), 26.35848190858241),
        ("Anexo J23 GEI diésel", "Emisiones A", lookup("Emisiones Consumo Final A", "J23"), 20.91980979353673),
    ]
    recs = []
    for leap, detalle, got, exp in checks:
        recs.append(
            {
                "funcion_LEAP_equivalente": leap,
                "detalle": detalle,
                "esperado": exp,
                "motor_a": got,
                "ok": abs(got - exp) <= 1e-9,
            }
        )
    return pd.DataFrame(recs)


def matrix_frame() -> pd.DataFrame:
    return pd.DataFrame(MATRIX)
