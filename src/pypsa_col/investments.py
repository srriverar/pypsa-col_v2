"""Plausible Colombian investment packages on the 18-subarea (or 7-hub) network.

These are illustrative UPME/FNCER-style options for the Streamlit explorer,
not a transmission expansion plan. Capex is order-of-magnitude USD 2024.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import numpy as np

from .gui_core import apply_levers, network_objective, resolve_network_nc
from .plotting import WORKSHOP_COLORS

_SOLAR = np.array(
    [0, 0, 0, 0, 0, 0.02, 0.12, 0.35, 0.58, 0.78, 0.90, 0.96, 0.98, 0.92, 0.78, 0.55, 0.28, 0.08, 0, 0, 0, 0, 0, 0]
)
_WIND = np.array(
    [0.55, 0.58, 0.60, 0.62, 0.60, 0.52, 0.42, 0.35, 0.32, 0.30, 0.33, 0.36, 0.40, 0.42, 0.45, 0.48, 0.50, 0.52, 0.55, 0.58, 0.60, 0.58, 0.56, 0.54]
)

MAX_CUSTOM_ITEMS = 40

# bus name fragments → 18-subarea, 7-hub, STN station, OSM
_BUS_HINTS = {
    "guajira": ("Guajira", "GUJ", "Cuestecitas", "Riohacha", "Colectora"),
    "cesar": ("Cesar", "La Loma", "El Paso", "Copey"),
    "santander": ("Santander", "NOR", "Ocaña", "Barranca"),
    "bogota": ("Bogotá", "Bogota", "CEN", "Bacata", "Torca", "Nueva Esperanza"),
    "bogotá": ("Bogotá", "Bogota", "CEN", "Bacata"),
    "atlantico": ("Atlántico", "Atlantico", "CAR", "Sabanalarga", "Tebsa"),
    "atlántico": ("Atlántico", "Atlantico", "CAR", "Sabanalarga"),
    "caribe": ("CAR", "Caribe", "Sabanalarga"),
    "antioquia": ("Antioquia", "NOR", "San Carlos", "Cerromatoso", "Porce"),
    "valle": ("Valle", "Yumbo", "Pance"),
    "huila": ("Huila", "Betania", "Tesalia"),
    "bolivar": ("Bolívar", "Bolivar", "Cartagena"),
    "bolívar": ("Bolívar", "Bolivar"),
    "magdalena": ("Magdalena", "Fundación", "Santa Marta"),
    "meta": ("Meta", "Banadia", "Chivor"),
}

# lon, lat centroids from El Modelo STN (for OSM 251 / nearest bus)
ZONE_XY = {
    "Antioquia": (-75.1596, 6.3507),
    "Atlántico": (-74.9184, 10.2981),
    "Bogotá": (-74.3874, 5.3794),
    "Bolívar": (-75.4768, 10.3796),
    "Boyacá": (-73.3165, 6.3163),
    "CQR": (-75.6092, 4.8803),
    "Cauca": (-76.5515, 3.0634),
    "Cesar": (-73.6931, 10.0935),
    "Córdoba-Sucre": (-75.6022, 8.6233),
    "Guajira": (-73.0124, 11.2216),
    "Huila": (-75.5905, 2.4269),
    "Magdalena": (-74.1585, 11.0138),
    "Meta": (-73.7362, 5.3028),
    "Nariño": (-76.9708, 1.2234),
    "Norte de Santander": (-72.6948, 7.7786),
    "Santander": (-73.3817, 6.9533),
    "Tolima": (-75.3242, 4.0611),
    "Valle": (-76.1606, 4.0102),
}

PACKAGES = {
    "wind_guajira": {
        "label": "Eólica La Guajira +500 MW",
        "kind": "generator",
        "carrier": "Wind Onshore",
        "p_nom": 500.0,
        "bus": "guajira",
        "marginal_cost": 0.2,
        "capex_musd": 500 * 1.4,
        "note": "FNCER / Colectora–Cuestecitas. Perfil eólico Caribe.",
    },
    "solar_cesar": {
        "label": "Solar Cesar +400 MW",
        "kind": "generator",
        "carrier": "Solar",
        "p_nom": 400.0,
        "bus": "cesar",
        "marginal_cost": 0.1,
        "capex_musd": 400 * 0.8,
        "note": "La Loma / El Paso. Recurso solar alto en Cesar.",
    },
    "solar_santander": {
        "label": "Solar Santander +300 MW",
        "kind": "generator",
        "carrier": "Solar",
        "p_nom": 300.0,
        "bus": "santander",
        "marginal_cost": 0.1,
        "capex_musd": 300 * 0.8,
        "note": "Entrega en Santander (no el atajo legacy Bogotá).",
    },
    "bess_bogota": {
        "label": "BESS Bogotá 200 MW / 4 h",
        "kind": "storage",
        "p_nom": 200.0,
        "max_hours": 4.0,
        "bus": "bogota",
        "capex_musd": 200 * 4 * 0.28,
        "note": "Pico de la demanda del centro; reduce shedding y térmica de punta.",
    },
    "tx_colectora": {
        "label": "Evacuación Guajira–Cesar +800 MW",
        "kind": "tx",
        "delta_mw": 800.0,
        "bus0": "guajira",
        "bus1": "cesar",
        "capex_musd": 800 * 0.45,
        "note": "Estilo Colectora: N-1 de evacuación eólica.",
    },
    "tx_costa_interior": {
        "label": "Refuerzo Caribe–Interior +600 MW",
        "kind": "tx",
        "delta_mw": 600.0,
        "bus0": "atlantico",
        "bus1": "bogota",
        "alt_bus0": "caribe",
        "alt_bus1": "cen",
        "capex_musd": 600 * 0.55,
        "note": "Alivia el corredor Costa–Centro ( Sabanalarga / Cerromatoso ).",
    },
    "coal_out": {
        "label": "Cierre de carbón (Costa y interior)",
        "kind": "coal_out",
        "capex_musd": 0.0,
        "note": "p_nom carbón = 0. Criterio de descarbonización UPME; sube gas/FNCER.",
    },
}


def _fold(name: str) -> str:
    return str(name).casefold()


def _zone_key(hint: str) -> str:
    h = _fold(hint).replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    for z in ZONE_XY:
        zf = _fold(z).replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        if h == zf or h in zf or zf in h:
            return z
    return hint


def _buses_in_zone(n, hint: str) -> list[str]:
    keys = list(_BUS_HINTS.get(hint.casefold(), ())) + [hint, _zone_key(hint)]
    names = list(n.buses.index.astype(str))
    hits: list[str] = []
    if "subarea" in n.buses.columns:
        sa = n.buses["subarea"].astype(str)
        for key in keys:
            k = _fold(key)
            for name in names:
                if k and k in _fold(str(sa.get(name, ""))):
                    hits.append(name)
    for key in keys:
        k = _fold(key)
        if len(k) < 3:
            continue
        for name in names:
            if k in _fold(name):
                hits.append(name)
    # unique preserve order
    out, seen = [], set()
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def _find_bus(n, hint: str) -> str | None:
    hits = _buses_in_zone(n, hint)
    if hits:
        if "v_nom" in n.buses.columns:
            try:
                return max(hits, key=lambda b: float(n.buses.at[b, "v_nom"] or 0))
            except Exception:
                return hits[0]
        return hits[0]
    zone = _zone_key(hint)
    xy = ZONE_XY.get(zone)
    if xy is not None and "x" in n.buses.columns and "y" in n.buses.columns:
        try:
            dx = n.buses.x.astype(float) - xy[0]
            dy = n.buses.y.astype(float) - xy[1]
            return str((dx * dx + dy * dy).astype(float).idxmin())
        except Exception:
            pass
    names = list(n.buses.index.astype(str))
    return names[0] if names else None


def _find_link(n, b0: str, b1: str) -> str | None:
    if n.links.empty:
        return None
    a_set = set(_buses_in_zone(n, b0) or ([_find_bus(n, b0)] if _find_bus(n, b0) else []))
    b_set = set(_buses_in_zone(n, b1) or ([_find_bus(n, b1)] if _find_bus(n, b1) else []))
    a_set = {x for x in a_set if x}
    b_set = {x for x in b_set if x}
    for name, row in n.links.iterrows():
        ends = {str(row.bus0), str(row.bus1)}
        if ends & a_set and ends & b_set:
            return name
    a, b = _find_bus(n, b0), _find_bus(n, b1)
    if a is None or b is None:
        return None
    for name, row in n.links.iterrows():
        ends = {_fold(row.bus0), _fold(row.bus1)}
        if {_fold(a), _fold(b)} <= ends:
            return name
    return None


def _strengthen_tx(n, zona: str, dest: str, mw: float, key: str) -> dict:
    """Raise link p_nom or STN/OSM line s_nom between two zones; else add a line."""
    info: dict = {"bus0": _find_bus(n, zona), "bus1": _find_bus(n, dest)}
    link = _find_link(n, zona, dest)
    if link is not None:
        n.links.at[link, "p_nom"] = float(n.links.at[link, "p_nom"]) + float(mw)
        info["link"] = link
        return info
    a_set = set(_buses_in_zone(n, zona))
    b_set = set(_buses_in_zone(n, dest))
    if not a_set and info.get("bus0"):
        a_set = {info["bus0"]}
    if not b_set and info.get("bus1"):
        b_set = {info["bus1"]}
    touched: list[str] = []
    if hasattr(n, "lines") and len(n.lines):
        for name, row in n.lines.iterrows():
            ends = {str(row.bus0), str(row.bus1)}
            if ends & a_set and ends & b_set:
                n.lines.at[name, "s_nom"] = float(row.s_nom) + float(mw)
                touched.append(str(name))
    if touched:
        info["link"] = touched[0]
        info["lines"] = touched
        return info
    a, b = info.get("bus0"), info.get("bus1")
    if a and b and a != b:
        lid = f"INV-{key}"
        try:
            if hasattr(n, "lines") and len(n.lines) and "s_nom" in n.lines.columns:
                v = float(n.buses.at[a, "v_nom"]) if "v_nom" in n.buses.columns else 230.0
                n.add("Line", lid, bus0=a, bus1=b, x=0.08, r=0.008, s_nom=float(mw), v_nom=v)
            else:
                n.add("Link", lid, bus0=a, bus1=b, p_nom=float(mw), p_min_pu=-1.0, efficiency=1.0, carrier="transport")
            info["link"] = lid
        except Exception:
            n.add("Link", lid, bus0=a, bus1=b, p_nom=float(mw), p_min_pu=-1.0, efficiency=1.0, carrier="transport")
            info["link"] = lid
    return info


def apply_packages(n, selected: list[str]) -> list[dict]:
    applied = []
    for key in selected:
        spec = PACKAGES.get(key)
        if not spec:
            continue
        kind = spec["kind"]
        if kind == "generator":
            bus = _find_bus(n, spec["bus"])
            gid = f"INV-{key}"
            n.add(
                "Generator",
                gid,
                bus=bus,
                p_nom=float(spec["p_nom"]),
                carrier=spec["carrier"],
                marginal_cost=float(spec["marginal_cost"]),
            )
            snaps = n.snapshots
            if spec["carrier"] == "Solar":
                profile = pd.Series(np.resize(_SOLAR, len(snaps)), index=snaps)
            elif spec["carrier"] == "Wind Onshore":
                profile = pd.Series(np.resize(_WIND, len(snaps)), index=snaps)
            else:
                profile = None
            if profile is not None:
                if "p_max_pu" in n.generators_t and not n.generators_t.p_max_pu.empty:
                    src = n.generators_t.p_max_pu.columns.intersection(
                        n.generators.index[n.generators.carrier == spec["carrier"]]
                    )
                    if len(src):
                        profile = n.generators_t.p_max_pu[src[0]].copy()
                        profile.name = gid
                extra = profile.rename(gid)
                if "p_max_pu" not in n.generators_t or n.generators_t.p_max_pu.empty:
                    n.generators_t.p_max_pu = extra.to_frame()
                elif gid not in n.generators_t.p_max_pu.columns:
                    n.generators_t.p_max_pu = pd.concat(
                        [n.generators_t.p_max_pu, extra], axis=1
                    )
            applied.append({**spec, "id": key, "bus": bus})
        elif kind == "storage":
            bus = _find_bus(n, spec["bus"])
            if "Pumped Hydro" not in n.carriers.index:
                n.add("Carrier", "Pumped Hydro", color=WORKSHOP_COLORS.get("Pumped Hydro", "lightseagreen"))
            n.add(
                "StorageUnit",
                f"INV-{key}",
                bus=bus,
                p_nom=float(spec["p_nom"]),
                max_hours=float(spec["max_hours"]),
                efficiency_store=0.92,
                efficiency_dispatch=0.92,
                cyclic_state_of_charge=True,
                carrier="Pumped Hydro",
                marginal_cost=0.5,
            )
            applied.append({**spec, "id": key, "bus": bus})
        elif kind == "tx":
            info = _strengthen_tx(n, spec["bus0"], spec["bus1"], float(spec["delta_mw"]), key)
            if info.get("link") is None and spec.get("alt_bus0"):
                info = _strengthen_tx(
                    n, spec["alt_bus0"], spec.get("alt_bus1", spec["bus1"]), float(spec["delta_mw"]), key
                )
            applied.append({**spec, "id": key, **info})
        elif kind == "coal_out":
            coal = n.generators.index[n.generators.carrier.isin({"Hard Coal", "Brown Coal", "Coal"})]
            if len(coal):
                n.generators.loc[coal, "p_nom"] = 0.0
            applied.append({**spec, "id": key, "units": int(len(coal))})
    return applied


def _kpis(n) -> dict:
    gen = n.generators_t.p if hasattr(n, "generators_t") and not n.generators_t.p.empty else pd.DataFrame()
    load = n.loads_t.p_set if hasattr(n, "loads_t") and not n.loads_t.p_set.empty else pd.DataFrame()
    if not n.snapshot_weightings.empty and "objective" in n.snapshot_weightings:
        w = n.snapshot_weightings["objective"]
    else:
        w = None
    if load.empty:
        demand = 0.0
    elif w is not None:
        demand = float((load.sum(axis=1).reindex(w.index).fillna(0) * w).sum())
    else:
        demand = float(load.sum().sum())
    mix = pd.Series(dtype=float)
    if not gen.empty:
        energy = gen.mul(w, axis=0) if w is not None else gen
        mix = energy.T.groupby(n.generators.carrier).sum().sum()
    shed = float(mix.get("load shedding", 0.0))
    re_car = {"Solar", "Wind Onshore", "Wind Offshore"}
    fnce = float(sum(mix.get(c, 0.0) for c in re_car))
    hydro = float(sum(mix.get(c, 0.0) for c in ("Storage Hydro", "Run of River", "Hydro")))
    coal = float(mix.get("Hard Coal", 0.0) + mix.get("Coal", 0.0))
    gas = float(mix.get("Gas", 0.0))
    return {
        "objective": network_objective(n),
        "demand_mwh": demand,
        "shed_mwh": shed,
        "fnce_mwh": fnce,
        "hydro_mwh": hydro,
        "coal_mwh": coal,
        "gas_mwh": gas,
        "fnce_pct": 100.0 * fnce / demand if demand else 0.0,
        "shed_pct": 100.0 * shed / demand if demand else 0.0,
        "mix": mix,
    }


ZONES_18 = (
    "Guajira", "Cesar", "Magdalena", "Atlántico", "Bolívar", "Córdoba-Sucre",
    "Antioquia", "CQR", "Valle", "Cauca", "Nariño", "Huila",
    "Tolima", "Bogotá", "Boyacá", "Santander", "Norte de Santander", "Meta",
)

INV_TYPES = {
    "Eólica": {"kind": "generator", "carrier": "Wind Onshore", "usd_per_kw": 1400, "mc": 0.2},
    "Solar": {"kind": "generator", "carrier": "Solar", "usd_per_kw": 800, "mc": 0.1},
    "Gas de respaldo": {"kind": "generator", "carrier": "Gas", "usd_per_kw": 900, "mc": 72.0},
    "BESS 4 h": {"kind": "storage", "usd_per_kw": 1120, "hours": 4.0},
    "Refuerzo de red": {"kind": "tx", "usd_per_kw": 500},
    "Cierre carbón (zona)": {"kind": "coal_zone", "usd_per_kw": 0.0},
}


def apply_custom_items(n, items: list[dict]) -> list[dict]:
    """User-placed alternatives: type + zone (+ dest zone for transmission)."""
    applied = []
    rows = [r for r in (items or []) if r]
    if len(rows) > MAX_CUSTOM_ITEMS:
        rows = rows[:MAX_CUSTOM_ITEMS]
    for i, row in enumerate(rows):
        tipo = str(row.get("tipo") or row.get("kind") or "").strip()
        spec = INV_TYPES.get(tipo)
        if not spec:
            continue
        mw = float(row.get("MW") or row.get("mw") or 0)
        zona = str(row.get("zona") or row.get("bus") or "").split("·")[0].strip()
        dest = str(row.get("zona_destino") or row.get("bus1") or "").split("·")[0].strip()
        key = f"custom-{i}-{tipo[:8]}"
        kind = spec["kind"]
        if kind == "generator" and mw > 0 and zona:
            fake = {
                "kind": "generator",
                "carrier": spec["carrier"],
                "p_nom": mw,
                "bus": zona,
                "marginal_cost": spec["mc"],
                "label": f"{tipo} {zona} +{mw:.0f} MW",
                "capex_musd": mw * spec["usd_per_kw"] / 1000.0,
                "note": "alternativa ubicada por el usuario",
            }
            bus = _find_bus(n, zona)
            gid = f"INV-{key}"
            n.add(
                "Generator", gid, bus=bus, p_nom=mw,
                carrier=spec["carrier"], marginal_cost=spec["mc"],
            )
            snaps = n.snapshots
            profile = None
            if spec["carrier"] == "Solar":
                profile = pd.Series(np.resize(_SOLAR, len(snaps)), index=snaps, name=gid)
            elif spec["carrier"] == "Wind Onshore":
                profile = pd.Series(np.resize(_WIND, len(snaps)), index=snaps, name=gid)
            if profile is not None:
                if "p_max_pu" not in n.generators_t or n.generators_t.p_max_pu.empty:
                    n.generators_t.p_max_pu = profile.to_frame()
                elif gid not in n.generators_t.p_max_pu.columns:
                    n.generators_t.p_max_pu = pd.concat([n.generators_t.p_max_pu, profile], axis=1)
            applied.append({**fake, "id": key, "bus": bus})
        elif kind == "storage" and mw > 0 and zona:
            bus = _find_bus(n, zona)
            if "Pumped Hydro" not in n.carriers.index:
                n.add("Carrier", "Pumped Hydro", color=WORKSHOP_COLORS.get("Pumped Hydro", "lightseagreen"))
            n.add(
                "StorageUnit", f"INV-{key}", bus=bus, p_nom=mw,
                max_hours=float(spec["hours"]), efficiency_store=0.92,
                efficiency_dispatch=0.92, cyclic_state_of_charge=True,
                carrier="Pumped Hydro", marginal_cost=0.5,
            )
            applied.append({
                "label": f"BESS {zona} {mw:.0f} MW / {spec['hours']:.0f} h",
                "id": key, "bus": bus, "p_nom": mw,
                "capex_musd": mw * spec["usd_per_kw"] / 1000.0,
                "note": "almacenamiento en la zona indicada",
            })
        elif kind == "tx" and mw > 0 and zona and dest:
            info = _strengthen_tx(n, zona, dest, mw, key)
            applied.append({
                "label": f"Enlace {zona}–{dest} +{mw:.0f} MW",
                "id": key, "delta_mw": mw,
                "capex_musd": mw * spec["usd_per_kw"] / 1000.0,
                "note": "refuerzo o nuevo corredor entre subáreas (links o líneas STN/OSM)",
                **info,
            })
        elif kind == "coal_zone" and zona:
            bus = _find_bus(n, zona)
            coal = n.generators.index[
                n.generators.carrier.isin({"Hard Coal", "Brown Coal", "Coal"})
                & n.generators.bus.map(lambda b: _fold(b) == _fold(bus) or _fold(zona) in _fold(b))
            ]
            if len(coal):
                n.generators.loc[coal, "p_nom"] = 0.0
            applied.append({
                "label": f"Cierre carbón en {zona}",
                "id": key, "bus": bus, "units": int(len(coal)),
                "capex_musd": 0.0, "note": "p_nom carbón = 0 en esa subárea",
            })
    return applied


def compare_investments(
    root: Path,
    selected: list[str],
    *,
    network_key: str = "clustered-18",
    levers: dict | None = None,
    solver: str = "highs",
    custom_items: list[dict] | None = None,
    draw_maps: bool = True,
) -> dict:
    """Solve baseline vs package on a copy of the chosen network."""
    import pypsa

    from .gui_core import NETWORKS, patch_linopy_pandas3

    patch_linopy_pandas3()
    key = network_key if network_key in NETWORKS else "clustered-18"
    path = resolve_network_nc(root, key)
    base = pypsa.Network()
    base.import_from_netcdf(path)
    if levers:
        apply_levers(base, levers)
    inv = pypsa.Network()
    inv.import_from_netcdf(path)
    if levers:
        apply_levers(inv, levers)
    applied = apply_packages(inv, selected)
    if custom_items:
        applied = list(applied) + apply_custom_items(inv, custom_items)
    from pathlib import Path as _P

    threads = 1 if _P("/mount/src").exists() else 2
    kwargs = {
        "solver_name": solver,
        "solver_options": {"threads": threads},
        "include_objective_constant": True,
    }
    try:
        b_status = base.optimize(**kwargs)
    except TypeError:
        kwargs.pop("include_objective_constant", None)
        b_status = base.optimize(**kwargs)
    i_status = inv.optimize(**kwargs)
    k0 = _kpis(base)
    k1 = _kpis(inv)
    capex = sum(float(PACKAGES[k]["capex_musd"]) for k in selected if k in PACKAGES)
    capex += sum(float(a.get("capex_musd") or 0) for a in applied if str(a.get("id", "")).startswith("custom"))
    mix0 = k0.pop("mix")
    mix1 = k1.pop("mix")
    mix = pd.DataFrame({"base": mix0, "con_inversion": mix1}).fillna(0.0)
    mix["delta"] = mix["con_inversion"] - mix["base"]
    opex_delta = k1["objective"] - k0["objective"]
    shed_delta = k1["shed_mwh"] - k0["shed_mwh"]
    fnce_delta = k1["fnce_mwh"] - k0["fnce_mwh"]
    maps: dict[str, str] = {}
    map_dir = ""
    if draw_maps:
        try:
            from datetime import datetime as _dt

            from .decision_maps import write_investment_maps

            dest = Path(root) / "outputs" / "investments" / _dt.now().strftime("%Y%m%d_%H%M%S")
            drawn = write_investment_maps(
                base, inv, Path(root), dest, applied,
                heading=f"{network_key} · {len(applied)} alternativas",
            )
            maps = {k: str(v) for k, v in drawn.items()}
            map_dir = str(dest)
        except Exception as exc:  # noqa: BLE001
            maps = {"error": str(exc)}
    return {
        "base_status": str(b_status[0] if isinstance(b_status, tuple) else b_status),
        "inv_status": str(i_status[0] if isinstance(i_status, tuple) else i_status),
        "kpis_base": k0,
        "kpis_inv": k1,
        "capex_musd": capex,
        "opex_delta": opex_delta,
        "shed_delta": shed_delta,
        "fnce_delta": fnce_delta,
        "mix_mwh": mix,
        "applied": applied,
        "network": network_key,
        "maps": maps,
        "map_dir": map_dir,
        "narrative": explain_investment(
            k0, k1, capex, opex_delta, shed_delta, fnce_delta, applied, levers or {}
        ),
    }


def compare_investments_multi(
    root: Path,
    selected: list[str],
    *,
    network_key: str = "clustered-18",
    cases: list[dict],
    solver: str = "highs",
    custom_items: list[dict] | None = None,
) -> dict:
    """Apply the same portfolio to every scenario × epoch under study."""
    if not cases:
        one = compare_investments(
            root, selected, network_key=network_key, solver=solver, custom_items=custom_items
        )
        return {"by_case": [], "primary": one, "n_cases": 1}
    rows = []
    primary = None
    for i, ep in enumerate(cases):
        r = compare_investments(
            root,
            selected,
            network_key=network_key,
            levers=ep,
            solver=solver,
            custom_items=custom_items,
            draw_maps=(i == 0),
        )
        k0, k1 = r["kpis_base"], r["kpis_inv"]
        rows.append(
            {
                "escenario": ep.get("global_scenario"),
                "época": ep.get("name"),
                "año": str(ep.get("start_date") or "")[:4],
                "demanda": ep.get("demand_scenario"),
                "hidrología": ep.get("hydrology_scenario"),
                "base_obj": k0.get("objective"),
                "inv_obj": k1.get("objective"),
                "Δopex": r["opex_delta"],
                "base_ENS_MWh": k0.get("shed_mwh"),
                "inv_ENS_MWh": k1.get("shed_mwh"),
                "ΔENS_MWh": r["shed_delta"],
                "base_FNCE_%": k0.get("fnce_pct"),
                "inv_FNCE_%": k1.get("fnce_pct"),
                "ΔFNCE_GWh": r["fnce_delta"] / 1e3,
                "base_status": r["base_status"],
                "inv_status": r["inv_status"],
            }
        )
        if primary is None:
            primary = r
            primary["levers_used"] = ep
    return {
        "by_case": rows,
        "primary": primary,
        "n_cases": len(cases),
        "network": network_key,
        "applied": (primary or {}).get("applied") or [],
        "capex_musd": (primary or {}).get("capex_musd") or 0.0,
    }


def explain_investment(
    k0: dict,
    k1: dict,
    capex_musd: float,
    opex_delta: float,
    shed_delta: float,
    fnce_delta: float,
    applied: list[dict],
    levers: dict,
) -> str:
    """Plain-language briefing for a UPME-style expansion decision (Motor B)."""
    lines = []
    lines.append("### Lectura para decisión de expansión")
    lines.append(
        f"Fondo: demanda **{levers.get('demand_scenario', '—')}**, "
        f"hidrología **{levers.get('hydrology_scenario', '—')}**, "
        f"clima **{levers.get('climate_scenario', '—')}**."
    )
    if applied:
        where = ", ".join(str(a.get("label") or a.get("id")) for a in applied[:12])
        lines.append(f"**Portafolio:** {where}.")
        lines.append(f"**Capex ilustrativo:** {capex_musd:,.0f} MUSD (orden de magnitud 2024, no PGE).")
    if opex_delta < -1:
        lines.append(
            f"**Operación:** el costo operativo baja {abs(opex_delta):,.0f} ud. del modelo. "
            "Suele indicar que la nueva energía o el enlace desplaza térmica cara o reduce ENS."
        )
    elif opex_delta > 1:
        lines.append(
            f"**Operación:** el costo operativo **sube** {opex_delta:,.0f}. "
            "El paquete no se paga solo en esta ventana (zona holgada, o respaldo térmico)."
        )
    else:
        lines.append("**Operación:** el costo casi no cambia; busque el valor en ENS o FNCE.")
    if shed_delta < -1:
        lines.append(
            f"**Seguridad de abastecimiento:** la energía no servida cae {abs(shed_delta):,.0f} MWh. "
            "En expansión esta es la señal más relevante después del costo."
        )
    elif k1.get("shed_mwh", 0) > 1 and shed_delta >= 0:
        lines.append(
            f"**Seguridad:** siguen {k1['shed_mwh']:,.0f} MWh no servidos. "
            "Falta potencia local, evacuación, o el crecimiento de demanda supera al paquete."
        )
    else:
        lines.append("**Seguridad:** no hay shedding material en esta formulación.")
    lines.append(
        f"**FNCE:** {k0.get('fnce_pct', 0):.1f}% → {k1.get('fnce_pct', 0):.1f}% de la demanda "
        f"({fnce_delta/1e3:+.1f} GWh). Indicador de política FNCER, no ENFICC."
    )
    coal0, coal1 = k0.get("coal_mwh", 0.0), k1.get("coal_mwh", 0.0)
    if coal1 < coal0 - 1:
        lines.append(f"**Carbón:** se desplazan {(coal0 - coal1)/1e3:.2f} GWh.")
    gas0, gas1 = k0.get("gas_mwh", 0.0), k1.get("gas_mwh", 0.0)
    if abs(gas1 - gas0) > 1:
        lines.append(f"**Gas:** {(gas1 - gas0)/1e3:+.2f} GWh.")
    if capex_musd > 0 and opex_delta < 0:
        years = capex_musd * 1e6 / abs(opex_delta)
        if 0 < years < 80:
            lines.append(
                f"**Payback operativo ilustrativo:** ~{years:.0f} años "
                "(capex / ahorro de la ventana modelada). No incluye tarifa ni confiabilidad."
            )
    lines.append(
        "**Qué no es:** no sustituye PET (N-1 AC), ni SDDP (valor del agua), ni ENFICC, "
        "ni un GEP con variables de inversión. Es **despacho de expansión (Motor B)** "
        "para comparar localización de alternativas."
    )
    if opex_delta < 0 or shed_delta < 0:
        lines.append(
            "**Sugerencia:** dejar el paquete en lista corta y rehacerlo bajo Niño / retraso de red "
            "(otro escenario en la GUI) antes de un estudio de transmisión."
        )
    else:
        lines.append("**Sugerencia:** cambiar zona o MW, o añadir el corredor de evacuación, y volver a comparar.")
    return "\n\n".join(lines)
