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

# bus name fragments → 18-subarea or 7-hub labels
_BUS_HINTS = {
    "guajira": ("Guajira", "GUJ"),
    "cesar": ("Cesar", "GUJ"),
    "santander": ("Santander", "NOR"),
    "bogota": ("Bogotá", "CEN"),
    "bogotá": ("Bogotá", "CEN"),
    "atlantico": ("Atlántico", "CAR"),
    "atlántico": ("Atlántico", "CAR"),
    "caribe": ("CAR",),
    "antioquia": ("Antioquia", "NOR"),
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


def _find_bus(n, hint: str) -> str | None:
    keys = _BUS_HINTS.get(hint.casefold(), (hint,))
    names = list(n.buses.index.astype(str))
    folded = [_fold(x) for x in names]
    for key in keys:
        k = key.casefold()
        for name, f in zip(names, folded):
            if f == k or k in f:
                return name
    return names[0] if names else None


def _find_link(n, b0: str, b1: str) -> str | None:
    a = _find_bus(n, b0)
    b = _find_bus(n, b1)
    if a is None or b is None or n.links.empty:
        return None
    for name, row in n.links.iterrows():
        ends = {_fold(row.bus0), _fold(row.bus1)}
        if {_fold(a), _fold(b)} <= ends or {_fold(a), _fold(b)} == ends:
            return name
        if _fold(a) in ends or _fold(b) in ends:
            # weaker: any link touching both regions via name fragments
            pass
    for name, row in n.links.iterrows():
        blob = f"{row.bus0} {row.bus1}".casefold()
        if b0.casefold()[:4] in blob and b1.casefold()[:4] in blob:
            return name
    return None


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
            link = _find_link(n, spec["bus0"], spec["bus1"])
            if link is None and spec.get("alt_bus0"):
                link = _find_link(n, spec["alt_bus0"], spec.get("alt_bus1", spec["bus1"]))
            if link is not None:
                n.links.at[link, "p_nom"] = float(n.links.at[link, "p_nom"]) + float(spec["delta_mw"])
            elif not n.links.empty:
                # add a new bidirectional link between the two buses
                a = _find_bus(n, spec["bus0"])
                b = _find_bus(n, spec.get("alt_bus1") or spec["bus1"])
                n.add(
                    "Link",
                    f"INV-{key}",
                    bus0=a,
                    bus1=b,
                    p_nom=float(spec["delta_mw"]),
                    p_min_pu=-1.0,
                    efficiency=1.0,
                    carrier="transport",
                )
                link = f"INV-{key}"
            applied.append({**spec, "id": key, "link": link})
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
    for i, row in enumerate(items):
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
            link = _find_link(n, zona, dest)
            if link is not None:
                n.links.at[link, "p_nom"] = float(n.links.at[link, "p_nom"]) + mw
            else:
                a, b = _find_bus(n, zona), _find_bus(n, dest)
                link = f"INV-{key}"
                n.add("Link", link, bus0=a, bus1=b, p_nom=mw, p_min_pu=-1.0, efficiency=1.0, carrier="transport")
            applied.append({
                "label": f"Enlace {zona}–{dest} +{mw:.0f} MW",
                "id": key, "link": link, "delta_mw": mw,
                "capex_musd": mw * spec["usd_per_kw"] / 1000.0,
                "note": "refuerzo o nuevo corredor entre subáreas",
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
) -> dict:
    """Solve baseline vs package on a copy of the chosen network."""
    import pypsa

    from .gui_core import patch_linopy_pandas3

    patch_linopy_pandas3()
    path = resolve_network_nc(root, network_key if network_key in ("clustered-18", "dashboard-sin", "stn-tesis") else "clustered-18")
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
    kwargs = {
        "solver_name": solver,
        "solver_options": {"threads": 2},
        "include_objective_constant": True,
    }
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
