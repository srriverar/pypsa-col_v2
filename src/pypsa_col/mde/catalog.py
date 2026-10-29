"""Classifications, fuels, GWP, FECOC-like emission factors.

Factors are documented order-of-magnitude for Motor A v1. They are NOT a
substitute for the official FECOC workbook of a given year. Each factor
records heating-value basis and source.
"""

from __future__ import annotations

FUELS = {
    "Bagazo": {"family": "biomasa", "biogenic_co2": True, "pci_gj_t": 7.5},
    "Carbón Mineral": {"family": "solido", "biogenic_co2": False, "pci_gj_t": 24.0},
    "Gas Natural": {"family": "gaseoso", "biogenic_co2": False, "pci_gj_dam3": 35.5},
    "Leña": {"family": "biomasa", "biogenic_co2": True, "pci_gj_t": 15.0},
    "Petróleo": {"family": "liquido", "biogenic_co2": False},
    "Residuos": {"family": "biomasa", "biogenic_co2": True},
    "Gasolina": {"family": "liquido", "biogenic_co2": False},
    "Diesel": {"family": "liquido", "biogenic_co2": False},
    "Carbón de Leña": {"family": "biomasa", "biogenic_co2": True},
    "Coque": {"family": "solido", "biogenic_co2": False},
    "Fuel Oil": {"family": "liquido", "biogenic_co2": False},
    "GLP": {"family": "gaseoso", "biogenic_co2": False},
    "Kerosene-Jet": {"family": "liquido", "biogenic_co2": False},
    "Electricidad_SIN": {"family": "electricidad", "biogenic_co2": False},
    "Electricidad_AUT_COG": {"family": "electricidad", "biogenic_co2": False},
    "Hidrogeno": {"family": "h2", "biogenic_co2": False},
    "Avgas": {"family": "liquido", "biogenic_co2": False},
}

# IPCC AR5 100-year GWP (common in NDC 2020 documentation). Record version.
GWP_AR5_100 = {"CO2": 1.0, "CH4": 28.0, "N2O": 265.0}
GWP_VERSION = "IPCC AR5 100 años"

# kg / TJ on NCV (PCI) — IPCC 2006 defaults rounded; FECOC should replace.
FE_KG_PER_TJ = {
    # gas, co2, ch4, n2o
    "Bagazo": {"CO2": 100_000.0, "CH4": 30.0, "N2O": 4.0},  # CO2 biogenic
    "Carbón Mineral": {"CO2": 94_600.0, "CH4": 1.0, "N2O": 1.5},
    "Gas Natural": {"CO2": 56_100.0, "CH4": 1.0, "N2O": 0.1},
    "Leña": {"CO2": 112_000.0, "CH4": 300.0, "N2O": 4.0},  # CO2 biogenic
    "Petróleo": {"CO2": 73_300.0, "CH4": 3.0, "N2O": 0.6},
    "Residuos": {"CO2": 100_000.0, "CH4": 30.0, "N2O": 4.0},
    "Gasolina": {"CO2": 69_300.0, "CH4": 3.0, "N2O": 0.6},
    "Diesel": {"CO2": 74_100.0, "CH4": 3.0, "N2O": 0.6},
    "Carbón de Leña": {"CO2": 112_000.0, "CH4": 200.0, "N2O": 4.0},
    "Coque": {"CO2": 107_000.0, "CH4": 1.0, "N2O": 1.5},
    "Fuel Oil": {"CO2": 77_400.0, "CH4": 3.0, "N2O": 0.6},
    "GLP": {"CO2": 63_100.0, "CH4": 1.0, "N2O": 0.1},
    "Kerosene-Jet": {"CO2": 71_500.0, "CH4": 3.0, "N2O": 0.6},
    "Avgas": {"CO2": 70_000.0, "CH4": 3.0, "N2O": 0.6},
    "Hidrogeno": {"CO2": 0.0, "CH4": 0.0, "N2O": 0.0},
    "Electricidad_SIN": {"CO2": 0.0, "CH4": 0.0, "N2O": 0.0},
    "Electricidad_AUT_COG": {"CO2": 0.0, "CH4": 0.0, "N2O": 0.0},
}

# Attributed electricity — inventory factor, NOT project/marginal.
# Order of magnitude of a hydro-heavy SIN; replace with UPME year-specific.
EF_ELEC_T_PER_MWH = 0.164  # tCO2e / MWh delivered (inventario ilustrativo)

# BECO 2023 published totals (F-DP-029 / portal UPME). Consumo final.
BECO_2023_PJ = {
    "transporte": 647.0,
    "industria": 346.0,
    "residencial": 283.0,
    # resto = agro + minero + construcción + no energético + comercial
    "terciario": 120.0,  # split of remainder — documented as reconstructed
    "agro_const_mineria": 80.0,
    "no_energetico": 53.0,
}
BECO_2023_TOTAL_PJ = 1529.0
BECO_2022_TOTAL_PJ = 1516.0
BECO_NOTE = (
    "Totales 2023=1529 PJ y 2022=1516 PJ: UPME BECO (F-DP-029). "
    "El desglose terciario/agro/no-energético del resto (253 PJ) es una "
    "reconciliación ilustrativa, no una celda oficial BECO."
)

# PAI-PROURE 2026–2035 preliminar (junio 2026) — contrast, not BECO copy.
PROURE_2024 = {
    "transporte_pj": 579.12,
    "residencial_share_final": 0.19,
    "residencial_coccion": 0.66,
    "residencial_refrigeracion": 0.17,
    "residencial_lena": 0.39,
    "residencial_elec": 0.29,
    "residencial_gn": 0.24,
    "residencial_glp": 0.07,
}

SECTORS = [
    "transporte",
    "industria",
    "residencial",
    "terciario",
    "agro_const_mineria",
    "no_energetico",
]

PEN_SCENARIOS = [
    "Actualización",
    "Modernización",
    "Inflexión",
    "Disrupción",
    "Transición límite superior",
    "Transición límite inferior",
]
