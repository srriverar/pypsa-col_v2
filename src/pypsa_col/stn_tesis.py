"""El Modelo STN (tesis Moreno) and the 18 operational-subarea aggregation.

The undergraduate GitHub dump (JuanMoreno2000/Tesis_RedTransmisionColombia)
ships ``RED_STN_COLOMBIA.nc`` as **125 buses / 193 lines / 0 transformers** —
the *proyecto base* that treated each substation as a single bus.

The master's thesis (2026) refines that into voltage-differentiated buses plus
PARATEC transformers and reports **147 buses / 206 lines / 34 transformers**.
That later PARATEC extract is not in the public repo. This module rebuilds the
same *method* from the published line list:

* parse every 220 / 230 / 500 kV circuit;
* one bus per (substation, kV);
* a transformer wherever a substation hosts two STN voltages
  (500/230 real, 220/230 fictitious bar-coupling as in §3.2);
* r, x in ohm (per-km × length) — the dumped ``.nc`` stored Ω/km by mistake;
* N-1 corridor rating = installed MVA minus the largest circuit.

The 18-subarea model follows §4: aggregate every STN bus into an XM-style
operational subarea, keep only inter-subarea corridors as bidirectional
``Link``s with N-1 capacity and a distance-proportional transmission cost.

Neither reconstruction is an official XM/UPME planning case.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

from .plotting import WORKSHOP_COLORS

LINE_NAME_RE = re.compile(
    r"^(.*?)\s+-\s+(.*?)\s+(\d+)\s+(\d+)\s*kV\s*$",
    re.IGNORECASE,
)

# XM-style 18 operational subareas used by CND (names, not official GIS).
SUBAREAS_18 = (
    "Guajira",
    "Cesar",
    "Magdalena",
    "Atlántico",
    "Bolívar",
    "Córdoba-Sucre",
    "Antioquia",
    "CQR",
    "Valle",
    "Cauca",
    "Nariño",
    "Huila",
    "Tolima",
    "Bogotá",
    "Boyacá",
    "Santander",
    "Norte de Santander",
    "Meta",
)

DEPT_TO_SUBAREA = {
    "LA GUAJIRA": "Guajira",
    "GUAJIRA": "Guajira",
    "CESAR": "Cesar",
    "MAGDALENA": "Magdalena",
    "ATLANTICO": "Atlántico",
    "ATLÁNTICO": "Atlántico",
    "BOLIVAR": "Bolívar",
    "BOLÍVAR": "Bolívar",
    "CORDOBA": "Córdoba-Sucre",
    "CÓRDOBA": "Córdoba-Sucre",
    "SUCRE": "Córdoba-Sucre",
    "ANTIOQUIA": "Antioquia",
    "CHOCO": "Antioquia",
    "CHOCÓ": "Antioquia",
    "CALDAS": "CQR",
    "QUINDIO": "CQR",
    "QUINDÍO": "CQR",
    "RISARALDA": "CQR",
    "VALLE DEL CAUCA": "Valle",
    "VALLE": "Valle",
    "CAUCA": "Cauca",
    "NARINO": "Nariño",
    "NARIÑO": "Nariño",
    "PUTUMAYO": "Nariño",
    "HUILA": "Huila",
    "CAQUETA": "Huila",
    "CAQUETÁ": "Huila",
    "TOLIMA": "Tolima",
    "CUNDINAMARCA": "Bogotá",
    "BOGOTA": "Bogotá",
    "BOGOTÁ": "Bogotá",
    "BOGOTA D.C.": "Bogotá",
    "BOYACA": "Boyacá",
    "BOYACÁ": "Boyacá",
    "SANTANDER": "Santander",
    "NORTE DE SANTANDER": "Norte de Santander",
    "NORTE SANTANDER": "Norte de Santander",
    "META": "Meta",
    "CASANARE": "Meta",
    "ARAUCA": "Meta",
    "VICHADA": "Meta",
}

KEYWORD_SUBAREA = {
    "Guajira": (
        "CUESTECITAS", "RIOHACHA", "MAICAO", "URIBIA", "COLECTORA", "GUAJIRA",
        "WINPESHI", "CASA ELECTRICA",
    ),
    "Cesar": (
        "LA LOMA", "EL COPEY", "VALLEDUPAR", "EL PASO", "BECERRIL", "CHIRIGUANA",
        "LA JAGUA",
    ),
    "Magdalena": (
        "FUNDACION", "SANTA MARTA", "RIO CORDOBA", "CIENAGA", "FUNDACIÓN",
        "TERMORIO", "PROELECTRICA",
    ),
    "Atlántico": (
        "SABANALARGA", "BARRANQUILLA", "TEBSA", "FLORES", "CARACOLI", "MALAMBO",
        "TERMOFLORES", "EL RIO",
    ),
    "Bolívar": (
        "CARTAGENA", "TERNERA", "BOLIVAR", "BOLÍVAR", "CANDELARIA", "MEMBRILLAL",
        "BAYUNCA",
    ),
    "Córdoba-Sucre": (
        "CERROMATOSO", "SAHAGUN", "SAHAGÚN", "MONTERIA", "MONTERÍA", "SINCELEJO",
        "TOLUVIEJO", "SAN MARCOS (COR", "CHINU", "CHINÚ",
    ),
    "Antioquia": (
        "SAN CARLOS", "GUATAPE", "GUATAPÉ", "PORCE", "ANCON", "ANCÓN", "PLAYAS",
        "GUADALUPE", "ITUANGO", "ANTIOQUIA", "PRIMAVERA", "GUATRON", "JAGUAS",
        "TASAJERA", "BELLO", "ENVIGADO", "BARBOSA", "LA SIERRA", "ESMERALDA",
        "CAUSO", "CERRO", "PURNIO", "MIEL",
    ),
    "CQR": (
        "LA VIRGINIA", "SAN FELIPE", "ARMENIA", "PEREIRA", "MANIZALES",
        "ESMERALDA", "IRRA", "EGEA", "CARTAGO",
    ),
    "Valle": (
        "YUMBO", "JUANCHITO", "SAN MARCOS (VALLE", "ALFEREZ", "ALFÉREZ",
        "OCCIDENTE", "CALIMA", "ALTO ANCHICAYA", "SAN BERNARDINO", "PANCE",
        "MELENDEZ", "YUMBO", "BALSILLAS",
    ),
    "Cauca": ("PATIA", "PATÍA", "SALVAJINA", "POPAYAN", "POPAYÁN", "MAYO"),
    "Nariño": (
        "PASTO", "JAMONDINO", "PUTUMAYO", "RENACER", "JAMONDINO", "IPIALES",
        "TUMACO",
    ),
    "Huila": (
        "BETANIA", "ALTAMIRA", "TESALIA", "EL QUIMBO", "GARZON", "GARZÓN",
        "PAICOL", "MIEL",
    ),
    "Tolima": (
        "MIROLINDO", "IBAGUE", "IBAGUÉ", "TULUNI", "ARMERO", "HONDA", "LERIDA",
        "DOIMA", "PRADO",
    ),
    "Bogotá": (
        "BACATA", "BACATÁ", "TORCA", "NUEVA ESPERANZA", "GUAVIO", "PARAISO",
        "PARAÍSO", "CIRCO", "GUACA", "LA GUACA", "CHORRERA", "BANANAL",
        "MESITA", "SOACHA", "TUNAL", "NOVA", "REFORMA", "CORZO",
    ),
    "Boyacá": ("CHIVOR", "PAIPA", "TUNJA", "SOGAMOSO", "CHIQUINQUIRA", "GUATEQUE"),
    "Santander": (
        "HIDROSOGAMOSO", "TASAJERO", "BARRANCA", "BARRANCABERMEJA", "SAN GIL",
        "BUCARAMANGA", "PALENQUE", "TERMOYOPAL", "CIMITARRA", "SAN ANTONIO",
    ),
    "Norte de Santander": (
        "OCAÑA", "OCAÑA", "SAN MATEO", "BELEN", "BELÉN", "CUCUTA", "CÚCUTA",
        "OCAÑA", "PRETINA", "INSULO",
    ),
    "Meta": (
        "ORIENTE", "APIAY", "VILLAVICENCIO", "SAN FERNANDO", "OCOA", "GUAYABETAL",
        "BANADIA", "BANADÍA", "SARAVENA", "YOPAL",
    ),
}

CARRIER_FROM_XM = {
    "AGUA": "Storage Hydro",
    "GAS": "Gas",
    "CARBON": "Hard Coal",
    "CARBÓN": "Hard Coal",
    "RAD SOLAR": "Solar",
    "SOLAR": "Solar",
    "VIENTO": "Wind Onshore",
    "EOLICA": "Wind Onshore",
    "EÓLICA": "Wind Onshore",
    "COMBUSTOLEO": "Oil",
    "ACPM": "Oil",
    "JET-A1": "Oil",
    "GLP": "Oil",
    "BAGAZO": "Waste",
    "BIOMASA": "Waste",
    "BIOGAS": "Waste",
    "BIOGÁS": "Waste",
}

MARGINAL_COST = {
    "Solar": 0.1,
    "Wind Onshore": 0.2,
    "Run of River": 6.0,
    "Storage Hydro": 8.0,
    "Waste": 25.0,
    "Hard Coal": 48.0,
    "Gas": 72.0,
    "Oil": 145.0,
    "load shedding": 8000.0,
}

TYPICAL_RXB = {
    220: (0.050, 0.40, 3.4),
    230: (0.048, 0.40, 3.5),
    500: (0.022, 0.30, 4.2),
}

PEAK_MW = 10_400.0
DEMAND_SHAPE = np.array(
    [
        0.72, 0.68, 0.66, 0.65, 0.66, 0.70, 0.78, 0.88,
        0.94, 0.96, 0.97, 0.98, 0.99, 0.98, 0.97, 0.96,
        0.97, 1.00, 0.99, 0.96, 0.92, 0.88, 0.82, 0.76,
    ]
)
SOLAR_SHAPE = np.array(
    [
        0, 0, 0, 0, 0, 0.02, 0.12, 0.35,
        0.58, 0.78, 0.90, 0.96, 0.98, 0.92, 0.78, 0.55,
        0.28, 0.08, 0, 0, 0, 0, 0, 0,
    ]
)
WIND_SHAPE = np.array(
    [
        0.55, 0.58, 0.60, 0.62, 0.60, 0.52, 0.42, 0.35,
        0.32, 0.30, 0.33, 0.36, 0.40, 0.42, 0.45, 0.48,
        0.50, 0.52, 0.55, 0.58, 0.60, 0.58, 0.56, 0.54,
    ]
)


def tesis_dir(root: Path) -> Path:
    return Path(root) / "data" / "tesis_stn"


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.upper()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def station_key(name: str) -> str:
    return fold(name)


def parse_line_name(operador: str) -> tuple[str, str, int, int] | None:
    m = LINE_NAME_RE.match(re.sub(r"\s+", " ", str(operador)).strip())
    if not m:
        return None
    a, b, circ, kv = m.group(1).strip(), m.group(2).strip(), int(m.group(3)), int(m.group(4))
    return a, b, circ, kv


def bus_id(station: str, kv: int) -> str:
    return f"{station} {kv} kV"


def _load_line_table(root: Path) -> pd.DataFrame:
    path = tesis_dir(root) / "Lineas_Transmisión(actualizado).xlsx"
    df = pd.read_excel(path)
    rows = []
    for _, row in df.iterrows():
        parsed = parse_line_name(row["OPERADOR"])
        if not parsed:
            continue
        a, b, circ, kv = parsed
        length = float(row["LONGITUD (km)"] or 0.0)
        amps = float(row["CAPACIDAD TRANSPORTE NOMINAL (A)"] or 0.0)
        r1 = float(row["R1 (Ω/km)"] or 0.0)
        x1 = float(row["X1 (Ω/km)"] or 0.0)
        b1 = float(row["B1 (uS/km)"] or 0.0)
        typ_r, typ_x, typ_b = TYPICAL_RXB.get(kv, (0.05, 0.4, 3.4))
        if not math.isfinite(r1) or r1 <= 0:
            r1 = typ_r
        if not math.isfinite(x1) or x1 <= 0:
            x1 = typ_x
        if not math.isfinite(b1) or b1 <= 0:
            b1 = typ_b
        if not math.isfinite(length) or length <= 0:
            length = 1.0
        s_nom = math.sqrt(3.0) * kv * max(amps, 1.0) / 1000.0
        rows.append(
            {
                "name": str(row["OPERADOR"]),
                "station0": a,
                "station1": b,
                "circ": circ,
                "v_nom": kv,
                "length": length,
                "r_ohm": r1 * length,
                "x_ohm": max(x1 * length, 0.01),
                "b_s": b1 * length * 1e-6,
                "s_nom": s_nom,
                "uso": row.get("USO", ""),
            }
        )
    return pd.DataFrame(rows)


def _load_substation_coords(root: Path) -> pd.DataFrame:
    js = json.loads((tesis_dir(root) / "SUBESTACIONES.json").read_text(encoding="utf-8"))
    recs = []
    for feat in js.get("features", []):
        a = feat.get("attributes") or {}
        recs.append(
            {
                "est": a.get("EST") or a.get("NOM_SUBEST") or "",
                "municipio": a.get("MUNICIPIO") or "",
                "departamento": a.get("DEPARTAMEN") or "",
                "v_nom": a.get("TENSION_NO"),
                "x": a.get("LONGITUD"),
                "y": a.get("LATITUD"),
            }
        )
    geo = pd.DataFrame(recs)
    geo["key"] = geo["est"].map(station_key)
    manual = pd.read_csv(tesis_dir(root) / "bus_coords_manual.csv")
    return geo, manual


def _lookup_xy(station: str, geo: pd.DataFrame, manual: pd.DataFrame) -> tuple[float, float]:
    key = station_key(station)
    hit = geo.loc[geo["key"] == key]
    if not hit.empty:
        x, y = float(hit.iloc[0]["x"]), float(hit.iloc[0]["y"])
        if math.isfinite(x) and math.isfinite(y) and abs(x) > 1 and abs(y) > 1:
            return x, y
    man = manual.loc[manual["name"].map(station_key) == key]
    if not man.empty:
        x, y = float(man.iloc[0]["x"]), float(man.iloc[0]["y"])
        if math.isfinite(x) and math.isfinite(y):
            return x, y
    # prefix / containment
    for _, row in geo.iterrows():
        gk = row["key"]
        if gk and (gk in key or key in gk):
            x, y = float(row["x"]), float(row["y"])
            if math.isfinite(x) and math.isfinite(y) and abs(x) > 1:
                return x, y
    for _, row in manual.iterrows():
        gk = station_key(row["name"])
        if gk and (gk in key or key in gk):
            return float(row["x"]), float(row["y"])
    return -74.08, 4.71


def _dept_for_station(station: str, geo: pd.DataFrame) -> str:
    key = station_key(station)
    hit = geo.loc[geo["key"] == key]
    if not hit.empty:
        return str(hit.iloc[0]["departamento"] or "")
    for _, row in geo.iterrows():
        gk = row["key"]
        if gk and (gk in key or key in gk):
            return str(row["departamento"] or "")
    return ""


def assign_subarea(station: str, geo: pd.DataFrame) -> str:
    name_u = fold(station)
    # keyword first for well-known plants (department GIS is incomplete)
    for area, words in KEYWORD_SUBAREA.items():
        for w in words:
            if fold(w) and fold(w) in name_u:
                return area
    dept = fold(_dept_for_station(station, geo))
    if dept in {fold(k): v for k, v in DEPT_TO_SUBAREA.items()}:
        mapping = {fold(k): v for k, v in DEPT_TO_SUBAREA.items()}
        return mapping[dept]
    mapping = {fold(k): v for k, v in DEPT_TO_SUBAREA.items()}
    for k, v in mapping.items():
        if k and k in dept:
            return v
    return "Bogotá"


def _mpode_load_shares(root: Path, station_names: list[str]) -> dict[str, float]:
    path = tesis_dir(root) / "MPODE-PYPSA.xlsx"
    df = pd.read_excel(path)
    grouped = df.groupby("Values_Bus")["..Load.."].mean()
    keys = {station_key(s): s for s in station_names}
    shares: dict[str, float] = defaultdict(float)
    for bus, load in grouped.items():
        k = station_key(bus)
        if k in keys:
            shares[keys[k]] += float(load)
        else:
            # try containment
            for sk, sn in keys.items():
                if k and (k in sk or sk in k):
                    shares[sn] += float(load)
                    break
    total = sum(shares.values())
    if total <= 0:
        return {s: 1.0 / len(station_names) for s in station_names}
    return {s: v / total for s, v in shares.items()}


def _match_gen_bus(raw_bus: str, buses: pd.DataFrame) -> str | None:
    if not isinstance(raw_bus, str) or not raw_bus.strip():
        return None
    k = station_key(raw_bus)
    # prefer highest voltage at that station
    cand = []
    for name, row in buses.iterrows():
        st = str(row.get("station") or name)
        if station_key(st) == k or k in station_key(st) or station_key(st) in k:
            cand.append((float(row["v_nom"]), name))
    if cand:
        cand.sort(reverse=True)
        return cand[0][1]
    return None


def _add_carriers(n: pypsa.Network) -> None:
    for name, color in WORKSHOP_COLORS.items():
        if name not in n.carriers.index:
            n.add("Carrier", name, color=color)


def _snapshots() -> pd.DatetimeIndex:
    return pd.date_range("2026-03-01", periods=24, freq="h")


def _attach_time(n: pypsa.Network, load_share_by_bus: dict[str, float]) -> None:
    snaps = _snapshots()
    n.set_snapshots(snaps)
    shape = pd.Series(DEMAND_SHAPE, index=snaps)
    remaining = [b for b in n.buses.index if b not in load_share_by_bus]
    if remaining:
        leftover = max(0.0, 1.0 - sum(load_share_by_bus.values()))
        extra = leftover / len(remaining) if leftover > 0 else 1e-4
        for b in remaining:
            load_share_by_bus[b] = extra
    tot = sum(load_share_by_bus.values()) or 1.0
    load_ids, load_buses = [], []
    p_set = {}
    for bus, share in load_share_by_bus.items():
        if bus not in n.buses.index:
            continue
        lid = f"d-{bus}"
        load_ids.append(lid)
        load_buses.append(bus)
        p_set[lid] = PEAK_MW * (share / tot) * shape
    if load_ids:
        n.add("Load", load_ids, bus=load_buses, p_set=0.0)
        n.loads_t.p_set = pd.DataFrame(p_set, index=snaps)

    solar = pd.Series(SOLAR_SHAPE, index=snaps)
    wind = pd.Series(WIND_SHAPE, index=snaps)
    hydro = pd.Series(np.full(24, 0.58), index=snaps)
    profiles = {}
    for g, row in n.generators.iterrows():
        if row.carrier == "load shedding":
            continue
        if row.carrier == "Solar":
            profiles[g] = solar
        elif row.carrier == "Wind Onshore":
            profiles[g] = wind
        elif row.carrier in {"Storage Hydro", "Run of River"}:
            profiles[g] = hydro
    if profiles:
        n.generators_t.p_max_pu = pd.DataFrame(profiles, index=snaps)

    shed_ids = [f"shed-{bus}" for bus in n.buses.index]
    n.add(
        "Generator",
        shed_ids,
        bus=list(n.buses.index),
        p_nom=8_000.0,
        carrier="load shedding",
        marginal_cost=MARGINAL_COST["load shedding"],
    )


def _add_generators(n: pypsa.Network, root: Path) -> None:
    path = tesis_dir(root) / "Generacion.xlsx"
    df = pd.read_excel(path)
    used: set[str] = set()
    for i, row in df.iterrows():
        name = str(row.get("Values_Name") or row.get("Values_Code") or f"gen-{i}")
        if name in used:
            name = f"{name}-{row.get('Values_Code')}"
        used.add(name)
        src = str(row.get("Values_EnerSource") or "GAS").strip().upper()
        carrier = CARRIER_FROM_XM.get(src, "Gas")
        p_nom = float(row.get("Values_Capacidad (MW)") or 0.0)
        if p_nom <= 0:
            continue
        bus = _match_gen_bus(row.get("Values_Bus"), n.buses)
        if bus is None:
            # drop on the electrically densest 230 kV Bogotá-ish bus
            bus = n.buses.index[0]
        n.add(
            "Generator",
            name,
            bus=bus,
            p_nom=p_nom,
            carrier=carrier,
            marginal_cost=MARGINAL_COST.get(carrier, 80.0),
        )
    # La Guajira wind not in the 76-row undergraduate plant table
    wind_bus = None
    for b in n.buses.index:
        if "CUESTECITAS" in fold(b) or "GUAJIRA" in fold(b):
            wind_bus = b
            break
    if wind_bus is not None and not any(n.generators.carrier == "Wind Onshore"):
        n.add(
            "Generator",
            "La Guajira wind (FNCER proxy)",
            bus=wind_bus,
            p_nom=500.0,
            carrier="Wind Onshore",
            marginal_cost=MARGINAL_COST["Wind Onshore"],
        )


def build_stn_physical(root: Path) -> pypsa.Network:
    """Voltage-differentiated STN from the published PARATEC line list."""
    root = Path(root)
    lines = _load_line_table(root)
    geo, manual = _load_substation_coords(root)
    n = pypsa.Network(name="El Modelo STN físico — PARATEC / tesis Moreno")
    _add_carriers(n)
    n.add("Carrier", "AC", color=WORKSHOP_COLORS.get("AC", "crimson"))

    stations: dict[str, set[int]] = defaultdict(set)
    xy: dict[str, tuple[float, float]] = {}
    subarea: dict[str, str] = {}
    for _, row in lines.iterrows():
        for st in (row.station0, row.station1):
            stations[st].add(int(row.v_nom))
            if st not in xy:
                xy[st] = _lookup_xy(st, geo, manual)
            if st not in subarea:
                subarea[st] = assign_subarea(st, geo)

    for st, voltages in stations.items():
        x, y = xy[st]
        area = subarea[st]
        for kv in sorted(voltages):
            bid = bus_id(st, kv)
            n.add("Bus", bid, v_nom=float(kv), x=x, y=y, carrier="AC")
            n.buses.loc[bid, "station"] = st
            n.buses.loc[bid, "subarea"] = area

    # transformers: one per pair of voltages at the same substation (§3.2)
    xfmr_i = 0
    for st, voltages in stations.items():
        ordered = sorted(voltages)
        for i, v0 in enumerate(ordered):
            for v1 in ordered[i + 1 :]:
                xfmr_i += 1
                # 500/230 ~ 450 MVA; 220/230 fictitious coupling ~ 800 MVA
                if {v0, v1} == {220, 230}:
                    s_nom, x_pu = 800.0, 0.015
                elif 500 in {v0, v1}:
                    s_nom, x_pu = 450.0, 0.12
                else:
                    s_nom, x_pu = 300.0, 0.10
                n.add(
                    "Transformer",
                    f"T-{st}-{v0}/{v1}",
                    bus0=bus_id(st, v0),
                    bus1=bus_id(st, v1),
                    s_nom=s_nom,
                    x=x_pu,
                    r=0.003,
                    tap_ratio=1.0,
                )

    # one Line per undirected corridor (station0, station1, kV); N-1 s_nom
    corridors: dict[tuple[str, str, int], list[pd.Series]] = defaultdict(list)
    for _, row in lines.iterrows():
        a, b = row.station0, row.station1
        if a == b:
            continue
        key = (min(a, b), max(a, b), int(row.v_nom))
        corridors[key].append(row)

    for (a, b, kv), members in corridors.items():
        s_all = [float(m.s_nom) for m in members]
        n1 = sum(s_all) - max(s_all) if len(s_all) >= 2 else s_all[0]
        # equivalent of parallels for r,x,b from the longest circuit
        longest = max(members, key=lambda m: m.length)
        n_par = float(len(members))
        name = f"{a} – {b} {kv} kV"
        n.add(
            "Line",
            name,
            bus0=bus_id(a, kv),
            bus1=bus_id(b, kv),
            r=float(longest.r_ohm) / n_par,
            x=max(float(longest.x_ohm) / n_par, 0.01),
            b=float(longest.b_s) * n_par,
            s_nom=max(n1, 50.0),
            length=float(longest.length),
            num_parallel=n_par,
            carrier="AC",
        )

    _add_generators(n, root)
    stations_list = list(stations)
    raw_shares = _mpode_load_shares(root, stations_list)
    load_share_by_bus: dict[str, float] = {}
    for st, share in raw_shares.items():
        volts = sorted(stations.get(st, []), reverse=True)
        if not volts:
            continue
        # dump demand on the highest-voltage bus of the station
        load_share_by_bus[bus_id(st, volts[0])] = share
    _attach_time(n, load_share_by_bus)
    n.meta = {
        "topology": "stn_physical_paratec_tesis",
        "electrical_kvl": True,
        "thesis_reported": {"buses": 147, "lines": 206, "transformers": 34},
        "this_extract": {
            "buses": int(len(n.buses)),
            "lines": int(len(n.lines)),
            "transformers": int(len(n.transformers)),
            "generators": int((n.generators.carrier != "load shedding").sum()),
        },
        "source": "JuanMoreno2000/Tesis_RedTransmisionColombia + tesis de maestría 2026 §3",
        "n_minus_1": "corridor s_nom = installed MVA − largest circuit",
        "note": (
            "Master's 147/206/34 uses a later PARATEC dump with explicit "
            "transformer records; this reconstruction uses the published "
            "220/230/500 kV line list and infers transformers at multi-kV sites."
        ),
    }
    return n


def _haversine_km(x0: float, y0: float, x1: float, y1: float) -> float:
    r = 6371.0
    p0, p1 = math.radians(y0), math.radians(y1)
    dp = math.radians(y1 - y0)
    dl = math.radians(x1 - x0)
    a = math.sin(dp / 2) ** 2 + math.cos(p0) * math.cos(p1) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def build_clustered18(root: Path, stn: pypsa.Network | None = None) -> pypsa.Network:
    """18 operational subareas as bidirectional Links (tesis §4)."""
    root = Path(root)
    if stn is None:
        stn = build_stn_physical(root)
    n = pypsa.Network(name="SIN · 18 subáreas operativas (tesis Moreno §4)")
    _add_carriers(n)
    n.add("Carrier", "AC", color=WORKSHOP_COLORS.get("AC", "crimson"))
    n.add("Carrier", "transport", color="#8093AD")

    buses = stn.buses.copy()
    if "subarea" not in buses.columns:
        raise ValueError("STN buses need a subarea column")
    centroids = (
        buses.groupby("subarea")
        .agg(x=("x", "mean"), y=("y", "mean"))
        .reindex(SUBAREAS_18)
        .dropna(how="all")
    )
    for area, row in centroids.iterrows():
        n.add("Bus", area, v_nom=220.0, x=float(row.x), y=float(row.y), carrier="AC")

    # N-1 then sum across distinct STN corridors between subareas
    pair_n1: dict[tuple[str, str], float] = defaultdict(float)
    for _, ln in stn.lines.iterrows():
        a0 = buses.at[ln.bus0, "subarea"]
        a1 = buses.at[ln.bus1, "subarea"]
        if a0 == a1 or a0 not in n.buses.index or a1 not in n.buses.index:
            continue
        pair = (min(a0, a1), max(a0, a1))
        # each STN corridor already stores N-1 s_nom
        pair_n1[pair] += float(ln.s_nom)

    for (a, b), p_nom in pair_n1.items():
        x0, y0 = n.buses.at[a, "x"], n.buses.at[a, "y"]
        x1, y1 = n.buses.at[b, "x"], n.buses.at[b, "y"]
        dist = _haversine_km(x0, y0, x1, y1)
        n.add(
            "Link",
            f"{a} – {b}",
            bus0=a,
            bus1=b,
            p_nom=max(p_nom, 50.0),
            p_min_pu=-1.0,
            efficiency=1.0,
            marginal_cost=0.002 * dist,
            carrier="transport",
            length=dist,
        )

    # generators follow their STN bus into the subarea
    for g, row in stn.generators.iterrows():
        if row.carrier == "load shedding":
            continue
        area = buses.at[row.bus, "subarea"]
        if area not in n.buses.index:
            continue
        n.add(
            "Generator",
            g,
            bus=area,
            p_nom=float(row.p_nom),
            carrier=row.carrier,
            marginal_cost=float(row.marginal_cost),
        )

    load_share: dict[str, float] = defaultdict(float)
    for lid, lrow in stn.loads.iterrows():
        area = buses.at[lrow.bus, "subarea"]
        if area not in n.buses.index:
            continue
        if not stn.loads_t.p_set.empty and lid in stn.loads_t.p_set:
            load_share[area] += float(stn.loads_t.p_set[lid].mean())
        else:
            load_share[area] += 1.0
    tot = sum(load_share.values()) or 1.0
    load_share = {k: v / tot for k, v in load_share.items()}
    _attach_time(n, load_share)
    n.meta = {
        "topology": "clustered_18_subareas",
        "electrical_kvl": False,
        "n_subareas": int(len(n.buses)),
        "links": int(len(n.links)),
        "source": "tesis Moreno 2026 §4 — aggregation of El Modelo STN",
        "n_minus_1": "sum of STN corridor N-1 ratings between subareas",
    }
    return n


def export_three_models(root: Path) -> dict:
    """Write STN + 18-subarea netCDF (the 7-hub already lives in dashboard-sin)."""
    root = Path(root)
    out = root / "data" / "streamlit" / "networks"
    out.mkdir(parents=True, exist_ok=True)
    stn = build_stn_physical(root)
    clustered = build_clustered18(root, stn)
    stn_path = out / "stn-tesis.nc"
    c18_path = out / "clustered-18.nc"
    stn.export_to_netcdf(stn_path)
    clustered.export_to_netcdf(c18_path)
    summary = {
        "stn": dict(stn.meta),
        "clustered18": dict(clustered.meta),
        "paths": {"stn": str(stn_path), "clustered18": str(c18_path)},
    }
    (out / "three_models.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    buses_csv = root / "data" / "tesis_stn" / "stn_buses.csv"
    stn.buses.reset_index().to_csv(buses_csv, index=False)
    return summary
