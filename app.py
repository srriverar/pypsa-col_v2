"""PyPSA-col — Streamlit dashboard with a faithful PyPSA-CL GUI as tab 1.

Runs PyPSA + HiGHS in the same process (unlike Netlify). Deploy:

    streamlit run app.py
    # or push this repo and set Streamlit Cloud main file = app.py

Tab 1 clones src/GUI.py / the browser GUI: presets C1–C3 / U1–U3, epoch queue,
six locked selectors, constraints, solver, sequential/parallel run_config, then
``gui_core.execute_run`` (levers + optimize + osm-interactive figures).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
os.environ.setdefault("MPLBACKEND", "Agg")
for _log_name in ("pypsa", "linopy", "linopy.io", "linopy.model", "linopy.constants"):
    logging.getLogger(_log_name).setLevel(logging.ERROR)

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from pypsa_col.charts import plot_series
from pypsa_col.st_compat import on_streamlit_cloud, stretch
from pypsa_col.gui_core import (
    ALL_GLOBAL_NAMES,
    BASE_COLORS,
    DEMAND_SCALE,
    HYDRO_SCALE,
    NETWORKS,
    PRESET_NAMES,
    SCENARIO_MAP,
    SCENARIO_NAMES,
    apply_levers,
    epoch_name_for,
    execute_run,
    flatten_user_data,
    patch_linopy_pandas3,
    resolve_network_nc,
    suggested_end_date,
)
from pypsa_col.plotting import NICE_NAME, STACK_ORDER, WORKSHOP_COLORS

NAVY = BASE_COLORS["fondo_azul_oscuro"]
CYAN = BASE_COLORS["cyan"]
ORANGE = BASE_COLORS["orange"]
MINT = BASE_COLORS["mint"]
SBG = BASE_COLORS["section_bg"]
INK = "#1b2a41"
PAPER = "#f4f1ea"
CARD = "#ffffff"

# XM/dashboard sheets are a fixed extract, not "last month".
DATA_WINDOW_START = "2024-01-01 00:00"
DATA_WINDOW_END = "2024-01-02 23:00"
XM_BUNDLE_START = "2023-12-31"
XM_BUNDLE_END = "2024-01-02"
DATA_TZ = "America/Bogota"

st.set_page_config(
    page_title="PyPSA-col — SIN Colombia",
    page_icon="🇨🇴",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _css() -> None:
    st.markdown(
        f"""
<style>
.stApp {{ background: {PAPER}; color: {INK}; }}
section[data-testid="stSidebar"] {{ background: {CARD}; }}
h1, h2, h3 {{ color: {INK} !important; }}
p, li, label, span, div {{ color: inherit; }}
[data-testid="stMarkdown"] p, [data-testid="stMarkdown"] li {{ color: {INK}; }}
[data-testid="stCaption"] {{ color: #3d4f63 !important; }}
[data-testid="stWidgetLabel"] p {{ color: {INK} !important; font-weight: 600; }}
div[data-testid="stMetricValue"] {{ color: #8a3b0f; }}
div[data-testid="stMetricLabel"] {{ color: #3d4f63; }}
.legend-box {{
  background: {CARD}; border: 1px solid #d9d2c5; border-left: 5px solid #b85716;
  padding: 10px 14px; color: {INK}; font-size: 0.95rem; line-height: 1.5;
}}
.date-box {{
  background: #fff8e8; border: 1px solid #e0c48a; border-left: 5px solid #b85716;
  padding: 10px 14px; color: {INK}; font-size: 0.95rem; line-height: 1.45;
  margin: 0 0 12px 0;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _data_window_banner(meta: dict | None = None) -> None:
    meta = meta or {}
    start = meta.get("start") or DATA_WINDOW_START
    end = meta.get("end") or DATA_WINDOW_END
    source = meta.get("source") or "extracto empaquetado"
    live = "live" in str(source).lower() or "SINERGOX" in str(source)
    title = (
        "XM — último mes cerrado (periodo D-1, no el mes calendario en curso)"
        if live
        else "XM — extracto de respaldo (no es el último mes cerrado)"
    )
    trimmed = meta.get("trimmed_days") or []
    trim_html = (
        f"<br><b>Aviso:</b> {meta.get('trim_reason')} La curva no incluye esos días."
        if trimmed
        else ""
    )
    st.markdown(
        f"""
<div class="date-box">
<b>{title}</b><br>
<b>Último mes cerrado:</b> <b>{start} → {end}</b> ({DATA_TZ}).
Convención XM / dashboard-sin-nodal: 30 días hasta <b>ayer (D-1)</b>, no el mes calendario
en curso ni “hoy” (la API publica el día incompleto).<br>
Fuente: {source}.
{trim_html}
La pestaña GUI (PyPSA-COL) usa la red PyPSA ya resuelta; estas hojas leen XM.
</div>
""",
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("epochs", [])
    ss.setdefault("scenarios", [])
    ss.setdefault("locked", False)
    ss.setdefault("global_scenario", PRESET_NAMES[0])
    ss.setdefault("custom_name", "")
    ss.setdefault("start_date", date(2026, 1, 1))
    cloud = on_streamlit_cloud()
    ss.setdefault("rep_years", 1 if cloud else 2)
    ss.setdefault("rep_months", 1 if cloud else 6)
    ss.setdefault("rep_days", 7)
    ss.setdefault("solver_threads", 1 if cloud else min(2, os.cpu_count() or 2))
    ss.setdefault("epoch_name", epoch_name_for(0))
    ss.setdefault("last_outdir", None)
    ss.setdefault("last_error", None)
    ss.setdefault("run_log", "")
    ss.setdefault("network_key", next(iter(NETWORKS)))
    ss.setdefault("cb_load_lost", False)
    ss.setdefault("max_load_lost", 2000.0)
    ss.setdefault("cb_discrete_tx", False)
    ss.setdefault("cb_fnce", False)
    ss.setdefault("fnce_pct", 20.0)
    ss.setdefault("cb_coal", False)
    ss.setdefault("full_horizon", False)
    ss.setdefault("solver_name", "highs")
    ss.setdefault("mip_gap", 0.1)
    ss.setdefault("lin_uc", True)
    ss.setdefault("exec_mode", "Secuencial")
    ss.setdefault("max_workers", 2)
    ss.setdefault("ram_limit", 85.0)
    vals = SCENARIO_MAP[PRESET_NAMES[0]]
    ss.setdefault("demand_scenario", vals["demand"])
    ss.setdefault("climate_scenario", vals["climate"])
    ss.setdefault("hydrology_scenario", vals["hydrology"])
    ss.setdefault("generation_investment_cost_scenario", vals["generation_investment_cost"])
    ss.setdefault("storage_investment_cost_scenario", vals["storage_investment_cost"])
    ss.setdefault("fuel_price_scenario", vals["fuel_price"])


def _apply_preset(name: str) -> None:
    if name == "Otro":
        return
    vals = SCENARIO_MAP[name]
    st.session_state.demand_scenario = vals["demand"]
    st.session_state.climate_scenario = vals["climate"]
    st.session_state.hydrology_scenario = vals["hydrology"]
    st.session_state.generation_investment_cost_scenario = vals["generation_investment_cost"]
    st.session_state.storage_investment_cost_scenario = vals["storage_investment_cost"]
    st.session_state.fuel_price_scenario = vals["fuel_price"]


def _settings_from_widgets() -> dict:
    gs = st.session_state.global_scenario
    label = (st.session_state.custom_name.strip() or "Otro") if gs == "Otro" else gs
    return {
        "global_scenario": label,
        "demand_scenario": st.session_state.demand_scenario,
        "climate_scenario": st.session_state.climate_scenario,
        "hydrology_scenario": st.session_state.hydrology_scenario,
        "generation_investment_cost_scenario": st.session_state.generation_investment_cost_scenario,
        "storage_investment_cost_scenario": st.session_state.storage_investment_cost_scenario,
        "fuel_price_scenario": st.session_state.fuel_price_scenario,
        "network": st.session_state.network_key,
        "solver_name": st.session_state.solver_name,
        "solver_threads": int(st.session_state.solver_threads),
        "solver_mip_gap": float(st.session_state.mip_gap),
        "linearized_unit_commitment": bool(st.session_state.lin_uc),
        "constraint_max_emissions": False,
        "max_emissions_MtCO2_year": 0.0,
        "constraint_max_load_lost": bool(st.session_state.cb_load_lost),
        "max_load_lost_GWh_year": float(st.session_state.max_load_lost) / 1000.0,
        "constraint_discrete_transmission_expansion": bool(st.session_state.cb_discrete_tx),
        "constraint_fnce": bool(st.session_state.cb_fnce),
        "fnce_pct": float(st.session_state.fnce_pct),
        "coal_phase_out": bool(st.session_state.cb_coal),
        "full_horizon": bool(st.session_state.full_horizon),
        "start_date": (
            st.session_state.start_date.isoformat()
            if hasattr(st.session_state.start_date, "isoformat")
            else str(st.session_state.start_date)[:10]
        ),
        "representative_years": int(st.session_state.rep_years),
        "representative_months": int(st.session_state.rep_months),
        "representative_days": int(st.session_state.rep_days),
    }


def _add_epoch() -> None:
    name = st.session_state.epoch_name.strip()
    if not name:
        st.session_state.last_error = "Por favor ingrese un nombre para la época."
        return
    if st.session_state.global_scenario == "Otro" and not st.session_state.custom_name.strip():
        st.session_state.last_error = 'Debe ingresar un nombre para el escenario "Otro".'
        return
    epochs = st.session_state.epochs
    if not epochs:
        start = st.session_state.start_date
    else:
        prev = datetime.strptime(epochs[-1]["end_date"], "%Y-%m-%d").date()
        start = prev + timedelta(days=1)
        st.session_state.start_date = start
    rep_y = int(st.session_state.rep_years)
    end_s = suggested_end_date(str(start), rep_y)
    ep = {
        **_settings_from_widgets(),
        "name": name,
        "start_date": start.isoformat() if hasattr(start, "isoformat") else str(start)[:10],
        "end_date": end_s,
        "representative_years": rep_y,
        "representative_months": int(st.session_state.rep_months),
        "representative_days": int(st.session_state.rep_days),
    }
    epochs.append(ep)
    st.session_state.locked = True
    nxt = datetime.strptime(end_s, "%Y-%m-%d").date() + timedelta(days=1)
    st.session_state.start_date = nxt
    st.session_state.epoch_name = epoch_name_for(len(epochs))
    st.session_state.last_error = None


def _remove_epoch() -> None:
    if not st.session_state.epochs:
        st.session_state.last_error = "Seleccione una época para eliminar."
        return
    idx = int(st.session_state.get("epoch_pick", 0))
    if 0 <= idx < len(st.session_state.epochs):
        st.session_state.epochs.pop(idx)
    st.session_state.epoch_name = epoch_name_for(len(st.session_state.epochs))
    if not st.session_state.epochs:
        st.session_state.locked = False
        st.session_state.start_date = date(2026, 1, 1)
    st.session_state.last_error = None


def _add_scenario() -> bool:
    if not st.session_state.epochs:
        st.session_state.last_error = (
            "Debe añadir al menos una época antes de agregar el escenario a la cola."
        )
        return False
    label = st.session_state.epochs[0]["global_scenario"]
    if label in [s["global_scenario"] for s in st.session_state.scenarios]:
        st.session_state.last_error = (
            f'Ya hay un escenario "{label}" en la cola. '
            'Para agregar una variante use "Otro" con un nombre distinto.'
        )
        return False
    st.session_state.scenarios.append(
        {"global_scenario": label, "epochs": [dict(e) for e in st.session_state.epochs]}
    )
    st.session_state.epochs = []
    st.session_state.locked = False
    st.session_state.custom_name = ""
    st.session_state.start_date = date(2026, 1, 1)
    st.session_state.rep_years = 2
    st.session_state.rep_months = 6
    st.session_state.rep_days = 7
    st.session_state.epoch_name = epoch_name_for(0)
    st.session_state.last_error = None
    return True


def _remove_scenario() -> None:
    if not st.session_state.scenarios:
        st.session_state.last_error = "Seleccione un escenario para eliminar de la cola."
        return
    idx = int(st.session_state.get("scenario_pick", 0))
    if 0 <= idx < len(st.session_state.scenarios):
        st.session_state.scenarios.pop(idx)
    st.session_state.last_error = None


def _run_all() -> None:
    if st.session_state.epochs:
        if not _add_scenario():
            return
    if not st.session_state.scenarios:
        st.session_state.last_error = (
            "Debe agregar al menos un escenario (con al menos una época) antes de ejecutar."
        )
        return
    try:
        workers = max(1, int(st.session_state.max_workers))
        ram = float(st.session_state.ram_limit)
        if not (10 <= ram <= 100):
            raise ValueError
    except ValueError:
        st.session_state.last_error = (
            "Revise la configuración de ejecución: Max parallel ≥ 1 y RAM entre 10 y 100."
        )
        return
    run_config = {
        "execution_mode": "parallel" if st.session_state.exec_mode == "Paralelo" else "sequential",
        "max_parallel_scenarios": workers,
        "ram_limit_pct": ram,
    }
    user_data = flatten_user_data(st.session_state.scenarios, run_config)
    try:
        outdir = execute_run(ROOT, user_data)
        st.session_state.last_outdir = str(outdir)
        st.session_state.last_error = None
        st.session_state.run_log = f"OK · {outdir}"
    except Exception as exc:  # noqa: BLE001
        st.session_state.last_error = str(exc)
        st.session_state.run_log = f"ERROR · {exc}"


def _latest_run() -> Path | None:
    """Session folder, else newest outputs/*/s*_e*."""
    out = st.session_state.get("last_outdir")
    if out:
        p = Path(out)
        if p.exists():
            return p
    root = ROOT / "outputs"
    if not root.exists():
        return None
    cands = [d for d in root.iterdir() if d.is_dir() and list(d.glob("s*_e*"))]
    if not cands:
        return None
    return max(cands, key=lambda d: d.stat().st_mtime)


def _colombia_maps() -> None:
    """Bundled Grid2Poster / atlas maps (not XM)."""
    fig = ROOT / "data" / "streamlit" / "figures"
    shown = 0
    for name, cap in (
        ("atlas_4panel.png", "Atlas 4 capas · fondo Grid2Poster (demanda / generación / LMP / flujos)"),
        ("atlas_demanda.png", "Demanda en el mapa de Colombia"),
        ("atlas_generacion.png", "Generación en el mapa de Colombia"),
        ("grid2poster_colombia.png", "Grid2Poster OSM Colombia"),
        ("sin_network.png", "SIN · naranja demanda · verde generación"),
        ("colombia_map.png", "Mapa de red"),
    ):
        p = fig / name
        if p.exists():
            st.image(str(p), caption=cap, **stretch())
            shown += 1
    if not shown:
        st.info("No hay PNG de mapas empaquetados en data/streamlit/figures.")


def _figure_dir() -> Path | None:
    if st.session_state.last_outdir:
        p = Path(st.session_state.last_outdir)
        dirs = sorted(p.glob("s*_e*"))
        if dirs:
            return dirs[-1]
    bundled = ROOT / "data" / "streamlit" / "figures"
    if bundled.exists():
        return bundled
    osm = ROOT / "results" / "osm-interactive"
    return osm if osm.exists() else None


def _show_png(path: Path, caption: str) -> None:
    if path.exists():
        st.image(str(path), caption=caption, **stretch())
    else:
        st.info(f"Aún no hay {path.name}. Corra un escenario en la GUI.")


def _show_html(path: Path, height: int = 540) -> None:
    if not path.exists():
        st.info(f"Aún no hay {path.name}.")
        return
    html = path.read_text(encoding="utf-8", errors="ignore")
    if len(html) > 4_500_000:
        st.caption(f"{path.name} es grande ({len(html)//1024} kB); se incrusta igual.")
    components.html(html, height=height, scrolling=True)


def _legend() -> None:
    st.markdown(
        """
<div class="legend-box">
<b>Cómo leer los círculos</b><br>
<span style="color:#f4a261">● Naranja</span> = <b>demanda</b> (DemaReal nacional partida entre barras). Todo bus tiene uno.<br>
<span style="color:#2a9d8f">● Verde-azulado</span> = <b>generación</b> (CEN de plantas XM colgadas a esa barra). Solo aparece donde hay planta.<br>
El <b>tamaño es proporcional al MW</b>. Interactivos:
<code>explore_load</code> = solo demanda;
<code>explore_capacity</code> = tartas por tecnología (colores workshop);
<code>explore_flow</code> = tamaño = generación, color de línea = carga %.<br>
Contorno geoBoundaries + San Andrés. Rojo = 500 kV, azul = 220/230 kV.
</div>
""",
        unsafe_allow_html=True,
    )


def _tab_gui_config() -> None:
    st.markdown(
        "Interfaz al estilo **PyPSA-CL**, pensada para un **comité UPME**: "
        "compare mundos (escenarios) y tramos de horizonte (épocas)."
    )
    st.markdown(
        """
<div class="legend-box">
<b>Escenario</b> = un futuro (C1 Niño, C2 BAU, U3 favorable…). Puede tener <b>varias épocas</b>.<br>
<b>Época</b> = un tramo de años <i>dentro</i> de ese futuro (corto 2026-30, mediano 2031-35).<br>
<b>Cola</b> = varios escenarios para comparar. <b>Run all</b> resuelve todos; el tablero y los mapas
salen en <i>Resumen de escenarios</i>.<br>
Las pestañas XM “último mes” <b>no</b> son estas épocas.
</div>
<div class="date-box">
<b>Alcance ahora (UPME Abierta · Motor B).</b> Esta app es el núcleo de
<b>expansión/operación eléctrica</b> con PyPSA + HiGHS. No sustituye LEAP (demanda de usos finales),
ni SDDP (hidrología estocástica), ni estudios AC N-1, ni ENFICC. Chile no “cambió LEAP+PLEXOS por PyPSA”:
introdujo PyPSA-CL para expansión eléctrica. Aquí hacemos lo mismo: un modelo eléctrico abierto, por funciones.
</div>
"""
        ,
        unsafe_allow_html=True,
    )
    if st.session_state.last_error:
        st.error(st.session_state.last_error)

    left, mid, right = st.columns([1.05, 1.15, 0.95], gap="medium")

    with left:
        st.subheader("Épocas (tramos del horizonte de ESTE escenario)")
        st.text_input("Nombre de la época (ej. Corto plazo 2026-2030):", key="epoch_name")
        st.date_input("Start date", key="start_date")
        end_s = suggested_end_date(str(st.session_state.start_date), int(st.session_state.rep_years))
        st.caption(f"End date (se sincroniza con representative years): **{end_s}**")
        st.selectbox("Representative years", [1, 2, 3, 4, 5], key="rep_years")
        st.selectbox("Representative months", [1, 2, 3, 4, 6, 12], key="rep_months")
        st.selectbox(
            "Representative days (1=típico · 2=laboral/finde · 7=lun–dom)",
            [1, 2, 7],
            key="rep_days",
        )
        net_labels = {k: v["label"] for k, v in NETWORKS.items()}
        st.selectbox(
            "Red Colombia",
            list(NETWORKS),
            format_func=lambda k: net_labels[k],
            key="network_key",
        )
        st.caption("Épocas ya añadidas a este escenario (aún no está en la cola hasta que pulse «Cerrar escenario»):")
        if st.session_state.epochs:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "i": i + 1,
                            "name": e["name"],
                            "start": e["start_date"],
                            "end": e["end_date"],
                            "yrs": e["representative_years"],
                            "months": e["representative_months"],
                            "days": e["representative_days"],
                        }
                        for i, e in enumerate(st.session_state.epochs)
                    ]
                ),
                hide_index=True,
                **stretch(),
            )
            st.selectbox(
                "Época seleccionada",
                list(range(len(st.session_state.epochs))),
                format_func=lambda i: st.session_state.epochs[i]["name"],
                key="epoch_pick",
            )
        else:
            st.caption("Ninguna época aún.")
        b1, b2 = st.columns(2)
        b1.button("Añadir época a este escenario", type="primary", on_click=_add_epoch)
        b2.button("Remove Selected", on_click=_remove_epoch)

    with mid:
        st.subheader("Escenario (el futuro / el mundo)")
        st.selectbox(
            "Global scenario:",
            ALL_GLOBAL_NAMES,
            key="global_scenario",
            disabled=st.session_state.locked,
            on_change=lambda: _apply_preset(st.session_state.global_scenario),
        )
        if st.session_state.locked:
            st.warning(
                "⚠ Locked after first epoch – add scenario to queue or remove all epochs to change"
            )
        if st.session_state.global_scenario == "Otro":
            st.text_input("Custom name:", key="custom_name")
        locked_sel = st.session_state.global_scenario != "Otro"
        st.selectbox("Demand scenario", SCENARIO_NAMES["demand"], key="demand_scenario", disabled=locked_sel)
        st.selectbox("Hydrology scenario", SCENARIO_NAMES["hydrology"], key="hydrology_scenario", disabled=locked_sel)
        st.selectbox("Climate scenario", SCENARIO_NAMES["climate"], key="climate_scenario", disabled=locked_sel)
        st.selectbox(
            "Generation investment cost",
            SCENARIO_NAMES["generation_investment_cost"],
            key="generation_investment_cost_scenario",
            disabled=locked_sel,
        )
        st.selectbox(
            "Storage investment cost",
            SCENARIO_NAMES["storage_investment_cost"],
            key="storage_investment_cost_scenario",
            disabled=locked_sel,
        )
        st.selectbox("Fuel price scenario", SCENARIO_NAMES["fuel_price"], key="fuel_price_scenario", disabled=locked_sel)

        st.subheader("Cola de escenarios (varios mundos, cada uno con sus épocas)")
        if st.session_state.scenarios:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "i": i + 1,
                            "global_scenario": s["global_scenario"],
                            "epochs": len(s["epochs"]),
                            "start": s["epochs"][0]["start_date"],
                            "end": s["epochs"][-1]["end_date"],
                        }
                        for i, s in enumerate(st.session_state.scenarios)
                    ]
                ),
                hide_index=True,
                **stretch(),
            )
            st.selectbox(
                "Escenario seleccionado",
                list(range(len(st.session_state.scenarios))),
                format_func=lambda i: st.session_state.scenarios[i]["global_scenario"],
                key="scenario_pick",
            )
        else:
            st.caption("Cola vacía.")
        c1, c2 = st.columns(2)
        c1.button("Cerrar escenario y ponerlo en la cola", on_click=_add_scenario)
        c2.button("Remove scenario", on_click=_remove_scenario)

        if st.button("Resolver todos los escenarios de la cola (HiGHS)", type="primary", key="btn_run_all"):
            with st.spinner(
                "HiGHS está resolviendo. Puede tardar 1–2 min por época. "
                "No recargue la página; el log de Manage app se llena con el simplex, no es un error."
            ):
                _run_all()
        if st.session_state.run_log:
            if str(st.session_state.run_log).startswith("ERROR"):
                st.error(st.session_state.run_log)
            else:
                st.success(st.session_state.run_log)

        js = None
        if st.session_state.scenarios or st.session_state.epochs:
            preview = list(st.session_state.scenarios)
            if st.session_state.epochs:
                preview = preview + [
                    {
                        "global_scenario": _settings_from_widgets()["global_scenario"],
                        "epochs": st.session_state.epochs,
                    }
                ]
            js = json.dumps(
                flatten_user_data(
                    preview,
                    {
                        "execution_mode": "sequential",
                        "max_parallel_scenarios": 1,
                        "ram_limit_pct": 85,
                    },
                ),
                ensure_ascii=False,
                indent=2,
            )
            st.download_button(
                "Descargar scenario.json (contrato PyPSA-CL)",
                js.encode("utf-8"),
                file_name="pypsa-col-scenario.json",
                mime="application/json",
            )

    with right:
        st.subheader("SIN Colombia")
        mapp = ROOT / "data" / "streamlit" / "figures" / "sin_network.png"
        if not mapp.exists():
            mapp = ROOT / "data" / "gui" / "sin_network.png"
        if mapp.exists():
            st.image(str(mapp), caption="naranja = demanda · verde = generación · 500 kV rojo / 220-230 azul")
        st.caption(
            "Equivale a `sen_network.png` de PyPSA-CL. Tres modelos: El Modelo STN, 18 subáreas, 7 nodos."
        )

    with st.expander("CONFIGURACIONES ADICIONALES", expanded=False):
        st.subheader("Restricciones adicionales")
        st.checkbox("Maximum load lost [MWh/year]", key="cb_load_lost")
        st.number_input("MWh/year:", min_value=0.0, key="max_load_lost")
        st.checkbox("Discrete transmission expansion", key="cb_discrete_tx")
        st.checkbox("Meta FNCE (renovables no convencionales)", key="cb_fnce")
        st.number_input("FNCE %:", min_value=0.0, max_value=100.0, key="fnce_pct")
        st.checkbox("Cierre de carbón (phase-out UPME)", key="cb_coal")
        st.checkbox(
            "Horizonte completo en redes grandes (STN 144 / OSM 251). "
            "Sin esto, v3 capa meses/días para que HiGHS quepa en Cloud.",
            key="full_horizon",
        )

        st.subheader("Configuración de optimización")
        st.selectbox("Solver name", ["highs", "cbc", "gurobi", "cplex"], key="solver_name")
        st.number_input("Threads", min_value=1, max_value=32, key="solver_threads")
        st.number_input("MIP gap", min_value=0.0, max_value=1.0, key="mip_gap")
        st.checkbox("Linearized unit commitment", key="lin_uc")

        st.subheader("Configuración de ejecución")
        st.selectbox("Execution mode", ["Secuencial", "Paralelo"], key="exec_mode")
        st.number_input("Max parallel scenarios", min_value=1, key="max_workers")
        st.number_input("RAM limit [% of total]", min_value=10.0, max_value=100.0, key="ram_limit")
        st.caption(
            "Paralelo: en Streamlit Cloud la corrida es secuencial dentro de esta sesión "
            "(un proceso). HiGHS corre aquí mismo. El Modelo STN ~segundos; 18 subáreas y 7 nodos más rápido."
        )


def _kpi_table(pairs: list[tuple[str, str]]) -> None:
    """Plain HTML KPIs — avoid st.metric (Arena/sandbox fails to fetch Metric.js)."""
    cells = "".join(
        f"<td style='padding:8px 14px;border:1px solid #d9d2c5;background:#fff'>"
        f"<div style='font-size:0.78rem;color:#3d4f63'>{k}</div>"
        f"<div style='font-size:1.15rem;font-weight:700;color:#1b2a41'>{v}</div></td>"
        for k, v in pairs
    )
    st.markdown(
        f"<table style='border-collapse:collapse;margin:6px 0 12px 0'><tr>{cells}</tr></table>",
        unsafe_allow_html=True,
    )


def _all_study_cases() -> list[dict]:
    """Every scenario × epoch in the queue, plus the scenario still being edited."""
    out: list[dict] = []
    seen: set[tuple] = set()
    for sc in st.session_state.get("scenarios") or []:
        gs = sc.get("global_scenario") or "escenario"
        for ep in sc.get("epochs") or []:
            d = dict(ep)
            d["global_scenario"] = d.get("global_scenario") or gs
            d["_source"] = "cola"
            d["_label"] = f"{d['global_scenario']} · {d.get('name')}"
            key = (d["global_scenario"], d.get("name"), d.get("start_date"), d.get("end_date"))
            seen.add(key)
            out.append(d)
    gs_edit = None
    try:
        gs_edit = _settings_from_widgets().get("global_scenario")
    except Exception:
        gs_edit = st.session_state.get("global_scenario")
    for ep in st.session_state.get("epochs") or []:
        d = dict(ep)
        d["global_scenario"] = d.get("global_scenario") or gs_edit
        key = (d.get("global_scenario"), d.get("name"), d.get("start_date"), d.get("end_date"))
        if key in seen:
            continue
        d["_source"] = "en edición"
        d["_label"] = f"{d.get('global_scenario')} · {d.get('name')} (edición)"
        out.append(d)
    if out:
        return out
    try:
        settings = _settings_from_widgets()
    except Exception:
        return []
    start = st.session_state.get("start_date") or date(2026, 1, 1)
    start_s = start.isoformat() if hasattr(start, "isoformat") else str(start)[:10]
    return [
        {
            "name": st.session_state.get("epoch_name") or "época en edición",
            "start_date": start_s,
            "end_date": suggested_end_date(start_s, int(st.session_state.get("rep_years") or 1)),
            "draft": True,
            "_source": "borrador",
            "_label": f"{settings.get('global_scenario')} · época en edición",
            **settings,
        }
    ]


def _epochs_under_study() -> list[dict]:
    return _all_study_cases()


def _rep_weights(ep: dict, n_snaps: int) -> dict:
    """Map the 24 h typical day onto a year / horizon (PyPSA snapshot_weightings)."""
    n_snaps = max(int(n_snaps), 1)
    n_years = int(ep.get("representative_years") or 1)
    n_months = int(ep.get("representative_months") or 1)
    n_days = int(ep.get("representative_days") or 1)
    hours_year = 8760.0
    w_h = hours_year / n_snaps  # 24 snapshots ⇒ each hour counts as 365 h/year
    return {
        "n_snaps": n_snaps,
        "weight_h": w_h,
        "n_years": n_years,
        "n_months": n_months,
        "n_days": n_days,
        "gwh_from_mw_sum": w_h / 1000.0,
    }


def _preview_network(ep: dict):
    import pypsa

    key = ep.get("network") or st.session_state.get("network_key") or "clustered-18"
    if key not in NETWORKS:
        key = "clustered-18"
    sig = (
        key,
        ep.get("demand_scenario"),
        ep.get("hydrology_scenario"),
        ep.get("climate_scenario"),
        ep.get("fuel_price_scenario"),
        ep.get("start_date"),
        ep.get("representative_years"),
        ep.get("representative_months"),
        ep.get("representative_days"),
        bool(ep.get("coal_phase_out")),
        ep.get("name"),
        ep.get("global_scenario"),
        "tb2-xm-shapes",
    )
    cache = st.session_state.setdefault("_net_cache", {})
    if sig in cache:
        return cache[sig]
    n = pypsa.Network()
    n.import_from_netcdf(resolve_network_nc(ROOT, key))
    apply_levers(n, ep)
    cache[sig] = (n, key)
    if len(cache) > 8:
        cache.pop(next(iter(cache)))
    return n, key


def _tab_gui_epoch_demand() -> None:
    st.markdown(
        "**Demanda de todas las épocas y escenarios** planteados en *Escenario y épocas* "
        "(cola + el escenario que esté editando). "
        "No confundir con la pestaña XM *Demanda* (último mes cerrado)."
    )
    epochs = _all_study_cases()
    if not epochs:
        st.info("Añada épocas y/o cierre escenarios en la primera subpestaña.")
        return
    rows = []
    for ep in epochs:
        dkey = ep.get("demand_scenario", "Media - C2")
        w = _rep_weights(ep, 24)
        rows.append(
            {
                "origen": ep.get("_source"),
                "escenario": ep.get("global_scenario"),
                "época": ep.get("name"),
                "demanda": dkey,
                "escala": DEMAND_SCALE.get(dkey, 1.0),
                "años_rep": w["n_years"],
                "meses_rep": w["n_months"],
                "días_rep": w["n_days"],
                "inicio": ep.get("start_date"),
                "fin": ep.get("end_date"),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, **stretch())
    st.markdown(
        """
<div class="date-box">
<b>Año representativo, no un solo 1 de marzo.</b> El <code>network.nc</code> trae
un <b>día típico de 24 h</b>. PyPSA-col lo <b>expande</b> a meses × tipos de día
(selectores <i>Representative months / days</i>) y asigna
<code>snapshot_weightings</code> para que Σ P·w ≈ energía anual.<br>
<b>Crecimiento entre épocas:</b> la tasa del escenario (C1 ~2 %/año … C3 ~3,8 %)
se <b>compone desde 2026</b> hasta el año de inicio de cada época. Una época 2031
en C2 no es el mismo MW que 2026: es (1,028)<sup>5</sup> veces más alta.<br>
<b>Referencias:</b> PyPSA <i>snapshot_weightings</i>; Hörsch, Brown et al., PyPSA-Eur;
PyPSA-CL (años / meses / días representativos).
</div>
""",
        unsafe_allow_html=True,
    )
    from pypsa_col.timebase import (
        annual_gwh,
        daily_profiles_mw,
        demand_growth_factor,
        growth_rate,
        monthly_system_mw,
    )

    series = {}
    energy = []
    monthly = {}
    daily = None
    daily_label = ""
    if not st.checkbox(
        "Graficar perfiles de demanda de la red (puede tardar)",
        value=False,
        key="dem_preview_net",
    ):
        st.info("Marque la casilla para ver lun–dom y la serie representativa.")
        return
    try:
        for ep in epochs:
            n, key = _preview_network(ep)
            if n.loads_t.p_set.empty:
                continue
            hourly = n.loads_t.p_set.sum(axis=1)
            label = ep.get("_label") or ep.get("name") or "época"
            series[label] = hourly.reset_index(drop=True)
            gwh_year = annual_gwh(n)
            g = demand_growth_factor(ep)
            r = growth_rate(ep.get("demand_scenario", "Media - C2"))
            n_years = int(ep.get("representative_years") or 1)
            energy.append(
                {
                    "escenario": ep.get("global_scenario"),
                    "época": ep.get("name"),
                    "año_época": str(ep.get("start_date") or "")[:4],
                    "red": NETWORKS[key]["label"],
                    "snapshots": int(len(hourly)),
                    "pico_MW": float(hourly.max()),
                    "valle_MW": float(hourly.min()),
                    "crecimiento_%/año": round(100 * r, 1),
                    "factor_vs_2026": round(g, 3),
                    "GWh_año": gwh_year,
                    "GWh_horizonte": gwh_year * n_years,
                }
            )
            m = monthly_system_mw(n)
            if not m.empty:
                monthly[label] = m
            dprof = daily_profiles_mw(n)
            if not dprof.empty:
                daily = dprof
                daily_label = label
    except Exception as exc:  # noqa: BLE001
        st.warning(f"No se pudo leer la red para previsualizar demanda: {exc}")
        return
    if monthly:
        st.subheader("Variación de la demanda a lo largo del año (MW medio por mes)")
        mdf = pd.DataFrame(monthly)
        mdf.index = [f"mes {i}" for i in mdf.index]
        plot_series(mdf, kind="bar", y_title="MW medio", x_title="Mes")
        st.caption(
            "Cada mes es un día (o lunes–domingo) representativo × estacionalidad tipo SIN. "
            "Entre épocas el nivel sube con la tasa del escenario (p. ej. C1 ~2%/año, C2 ~2.8%, C3 ~3.8%) "
            "compuesta desde 2026 hasta el año de inicio de la época."
        )
    if daily is not None and not daily.empty:
        st.subheader(f"Perfil diario por día de la semana — {daily_label}")
        plot_series(daily, kind="line", y_title="MW", x_title="Hora (0–23)")
        st.caption(
            "Forma tipo XM DemaReal / SIN: valle 03–05 h, rampa 6–9, pico 18–20 h. "
            "Lunes–viernes más altos; sábado más plano; **domingo** claramente más bajo. "
            "En *Escenario y épocas* elija Representative days = 7. "
            "No es el último mes XM (esa pestaña es el observado)."
        )
        st.dataframe(daily.round(1), **stretch())
    if series:
        chart = pd.DataFrame(series)
        st.subheader("Serie representativa completa (meses × tipos de día × 24 h)")
        plot_series(chart, kind="line", y_title="MW", x_title="Snapshot (mes × día × hora)")
        st.caption(
            "Cada color es un **escenario × época**. Clic en la leyenda para ocultar una. "
            "No es un único 1 de marzo: con 6 meses y 7 días verá 6×7×24 puntos. "
            "HiGHS usa los mismos snapshots y snapshot_weightings."
        )


def _tab_gui_epoch_generation() -> None:
    st.markdown(
        "**Generación de las épocas bajo estudio**: capacidad y disponibilidad "
        "(hidrología Niño/Niña, cierre de carbón) sobre la red elegida. "
        "La pestaña XM *Generación* es el **último mes cerrado**, no estas épocas."
    )
    st.markdown(
        """
<div class="date-box">
<b>¿La generación crece entre épocas?</b> Tres cosas distintas:<br>
<b>1. Demanda (GWh / MW de carga)</b> — <i>sí crece</i>. Tasa del escenario (C1 ~2 %/año,
C2 ~2,8 %, C3 ~3,8 %; U1–U3 análogas) <b>compuesta desde 2026</b> hasta el año de inicio
de la época. Eso está en <i>Demanda de las épocas</i>.<br>
<b>2. Capacidad instalada p_nom (MW)</b> — <i>no crece sola</i>. El inventario es el del
<code>network.nc</code>. Solo cambia si usted activa <b>cierre de carbón</b> o un paquete en
<i>Inversiones</i>. No hay GEP endógeno ni “% UPME” inventado. Costos de inversión
Alto/Medio/Bajo ponderan un GEP si se modelara; aquí no construyen MW.<br>
<b>3. Energía disponible / despacho</b> — la hidro/solar/eólica <i>sí</i> cambian con Niño/Niña
y estacionalidad (<code>p_max_pu</code>). El mix despachado (MWh) solo aparece <b>después de HiGHS</b>
y puede subir porque la demanda subió (más térmica), no porque se hayan añadido plantas.
</div>
""",
        unsafe_allow_html=True,
    )
    epochs = _all_study_cases()
    if not epochs:
        st.info("Añada épocas y/o cierre escenarios en *Escenario y épocas*.")
        return
    frames = []
    last_by = None
    last_label = ""
    if not st.checkbox(
        "Cargar disponibilidad de la red (p_nom × p_max_pu)",
        value=False,
        key="gen_preview_net",
    ):
        st.info("Marque la casilla para las curvas de disponibilidad. El despacho HiGHS se busca abajo si ya hay corrida.")
        out = _latest_run()
        if out:
            st.caption(f"Última corrida: `{out}`")
        return
    try:
        for ep in epochs:
            n, key = _preview_network(ep)
            gens = n.generators[n.generators.carrier != "load shedding"]
            cap = gens.groupby("carrier")["p_nom"].sum()
            w = _rep_weights(ep, len(n.snapshots))
            frames.append(
                pd.DataFrame(
                    {
                        "origen": ep.get("_source"),
                        "escenario": ep.get("global_scenario"),
                        "época": ep.get("name"),
                        "hidrología": ep.get("hydrology_scenario"),
                        "clima": ep.get("climate_scenario"),
                        "carbón_off": bool(ep.get("coal_phase_out")),
                        "años_rep": w["n_years"],
                        **{NICE_NAME.get(c, c): float(v) for c, v in cap.items()},
                    },
                    index=[0],
                )
            )
            label = ep.get("_label") or ep.get("name") or "época"
            if "p_max_pu" in n.generators_t and not n.generators_t.p_max_pu.empty:
                pu = n.generators_t.p_max_pu
                pnom = gens["p_nom"]
                cols = pu.columns.intersection(pnom.index)
                mw = pu[cols].mul(pnom.reindex(cols), axis=1)
                by = mw.T.groupby(gens.carrier).sum().T
                by = by.rename(columns=lambda c: NICE_NAME.get(c, c))
                last_by = by
                last_label = label
    except Exception as exc:  # noqa: BLE001
        st.warning(f"No se pudo previsualizar generación: {exc}")
        return
    if frames:
        st.dataframe(pd.concat(frames, ignore_index=True), hide_index=True, **stretch())
    if last_by is not None and not last_by.empty:
        st.subheader(f"Disponibilidad por tecnología — {last_label}")
        plot = last_by.reset_index(drop=True)
        order = [NICE_NAME.get(c, c) for c in STACK_ORDER if NICE_NAME.get(c, c) in plot.columns]
        rest = [c for c in plot.columns if c not in order]
        plot_series(plot[order + rest], kind="area", y_title="MW disponibles")
        st.caption("p_nom × p_max_pu (aún no es el despacho HiGHS; corra la cola para el mix óptimo).")
        try:
            months = pd.Series(last_by.index.month, index=last_by.index)
            if months.nunique() > 1:
                st.subheader("Disponibilidad media por mes (MW)")
                plot_series(last_by.groupby(last_by.index.month).mean(), kind="bar", y_title="MW", x_title="Mes")
        except Exception:
            pass
    st.subheader("Despacho HiGHS de la última corrida")
    out = _latest_run()
    shown_dispatch = False
    if out:
        st.caption(f"Carpeta: `{out}`")
        ep_dirs = sorted(Path(out).glob("s*_e*"))
        for epd in ep_dirs:
            mix = epd / "generation_by_carrier.csv"
            if mix.exists():
                df = pd.read_csv(mix, index_col=0, parse_dates=True)
                df = df.rename(columns=lambda c: NICE_NAME.get(c, c))
                st.markdown(f"**{epd.name}**")
                plot_series(df, kind="area", y_title="MW despachados")
                shown_dispatch = True
            atlas = epd / "atlas_4panel.png"
            if atlas.exists():
                st.image(str(atlas), caption=f"Mapa Colombia · {epd.name}", **stretch())
    if not shown_dispatch:
        st.info(
            "Todavía no hay `generation_by_carrier.csv`. En *Escenario y épocas* pulse "
            "«Resolver todos los escenarios» (HiGHS). El gráfico de arriba es disponibilidad, no despacho."
        )
        bundled = ROOT / "data" / "streamlit" / "figures" / "dispatch.png"
        if bundled.exists():
            st.image(str(bundled), caption="Ejemplo empaquetado (no es su corrida)", **stretch())
        _colombia_maps()


def _tab_gui_figures() -> None:
    st.header("Mapas y figuras **por escenario y época**")
    st.caption(
        "Cada corrida HiGHS deja un atlas (demanda, generación, LMP, flujos) "
        "y las figuras osm-interactive. Se agrupan por escenario."
    )
    _legend()
    out = st.session_state.get("last_outdir")
    folders = sorted(Path(out).glob("s*_e*")) if out else []
    if not folders:
        figdir = _figure_dir()
        if figdir is None:
            st.info("Corra uno o más escenarios (cola → Resolver). Aquí aparecerán mapas **por escenario**.")
            bundled = ROOT / "data" / "streamlit" / "figures" / "atlas_4panel.png"
            if bundled.exists():
                st.image(str(bundled), caption="Atlas ilustrativo (aún no es su corrida)", **stretch())
            return
        folders = [figdir]
    by_sc: dict[str, list] = {}
    for epd in folders:
        title = epd.name
        meta = epd / "run_metadata_log.csv"
        sc_name = "escenario"
        ep_name = epd.name
        if meta.exists():
            m = pd.read_csv(meta)
            if not m.empty:
                sc_name = str(m.iloc[0].get("global_scenario") or sc_name)
                ep_name = str(m.iloc[0].get("name") or ep_name)
                title = f"{sc_name} · {ep_name}"
        by_sc.setdefault(sc_name, []).append((title, epd))
    for sc_name, items in by_sc.items():
        st.subheader(f"Escenario: {sc_name}")
        for title, epd in items:
            with st.expander(title, expanded=len(items) == 1 and len(by_sc) == 1):
                board = epd / "atlas_4panel.png"
                if board.exists():
                    st.image(str(board), caption="Atlas 4 capas", **stretch())
                layer_opts = [
                    ("atlas_demanda.png", "Demanda"),
                    ("atlas_generacion.png", "Generación"),
                    ("atlas_lmp.png", "LMP"),
                    ("atlas_flujos.png", "Flujos"),
                    ("colombia_map.png", "Red"),
                    ("lmp.png", "LMP legado"),
                    ("dispatch.png", "Despacho"),
                ]
                available = [(f, cap) for f, cap in layer_opts if (epd / f).exists()]
                if available:
                    pick = st.selectbox(
                        "Ampliar capa",
                        [f for f, _ in available],
                        format_func=lambda f: dict(available)[f],
                        key=f"fig-layer-{epd.name}",
                    )
                    st.image(str(epd / pick), **stretch())
                _show_html(epd / "explore_load.html")
                _show_html(epd / "explore_flow.html")


def _tab_gui_scenario_summary() -> None:
    from pypsa_col.timebase import annual_gwh, demand_growth_factor, growth_rate

    st.markdown(
        "**Tablero de decisión.** Cada fila es una **época**; las filas que comparten "
        "el mismo escenario son tramos del mismo futuro. Si corrió varios escenarios, "
        "compárelos aquí (costo, energía no servida, FNCE) y abra el **atlas de Colombia** "
        "(demanda, generación, LMP, flujos) de cada uno."
    )
    st.subheader("Resumen por escenario × época")
    st.caption(
        "Antes de HiGHS no hay `objective_usd`. La demanda crece con el escenario; "
        "`p_nom` no se infla solo. Un error de una época no se pega a la siguiente."
    )
    epochs = _all_study_cases()
    rows: list[dict] = []
    if not epochs:
        st.info("Añada épocas en *Escenario y épocas*.")
    for ep in epochs:
        rec = {
            "escenario": ep.get("global_scenario") or "—",
            "época": ep.get("name") or "—",
            "año": str(ep.get("start_date") or "")[:4],
            "demanda": ep.get("demand_scenario") or "—",
            "hidro": ep.get("hydrology_scenario") or "—",
            "carbón_off": bool(ep.get("coal_phase_out")),
            "tasa_%/a": None,
            "factor_vs_2026": None,
            "GWh_año": None,
            "p_nom_MW": None,
            "objective_usd": "— (sin HiGHS)",
            "nota": "",
        }
        try:
            dkey = ep.get("demand_scenario", "Media - C2")
            rec["tasa_%/a"] = round(100 * growth_rate(dkey), 1)
            rec["factor_vs_2026"] = round(demand_growth_factor(ep), 3)
        except Exception as exc:  # noqa: BLE001
            rec["nota"] = str(exc)
        rows.append(rec)
    if st.checkbox(
        "Calcular GWh y p_nom (carga las redes; no al abrir)",
        value=False,
        key="sum_preview_net",
    ):
        for rec, ep in zip(rows, epochs):
            try:
                n, key = _preview_network(ep)
                gens = n.generators
                if len(gens) and "carrier" in gens.columns:
                    gens = gens[gens.carrier != "load shedding"]
                rec["p_nom_MW"] = (
                    float(gens["p_nom"].sum()) if len(gens) and "p_nom" in gens.columns else 0.0
                )
                rec["GWh_año"] = annual_gwh(n)
                rec["red"] = NETWORKS.get(key, {}).get("label", key)
            except Exception as exc:  # noqa: BLE001
                rec["nota"] = f"error de previsualización: {exc}"

    out = st.session_state.get("last_outdir") or (_latest_run() and str(_latest_run()))
    cost_map: dict[tuple, dict] = {}
    if out:
        rootp = Path(out)
        costs = rootp / "system_costs.csv"
        if costs.exists():
            try:
                cdf = pd.read_csv(costs)
                if "objective_usd" in cdf.columns:
                    cdf["objective_usd"] = pd.to_numeric(cdf["objective_usd"], errors="coerce")
                for _, r in cdf.iterrows():
                    cost_map[(str(r.get("global_scenario")), str(r.get("epoch")))] = r.to_dict()
            except Exception as exc:  # noqa: BLE001
                st.warning(f"No se pudo leer system_costs.csv: {exc}")
        for rec in rows:
            hit = cost_map.get((str(rec["escenario"]), str(rec["época"])))
            if not hit:
                continue
            obj = hit.get("objective_usd")
            rec["objective_usd"] = float(obj) if obj is not None and pd.notna(obj) else "—"
            if hit.get("demand_gwh") not in (None, "") and rec.get("GWh_año") in (None,):
                rec["GWh_año"] = hit.get("demand_gwh")

    if rows:
        view = pd.DataFrame(rows)
        st.dataframe(view, hide_index=True, **stretch())
        chart_src = view.dropna(subset=["GWh_año"]) if "GWh_año" in view.columns else pd.DataFrame()
        if not chart_src.empty:
            lab = chart_src["escenario"].astype(str) + " · " + chart_src["época"].astype(str)
            plot_series(
                pd.Series(chart_src["GWh_año"].to_numpy(), index=lab, name="GWh_año"),
                kind="bar",
                y_title="GWh (año representativo)",
            )
            st.caption("GWh de demanda del año representativo (ponderado). No es objective_usd.")
        pnom = view.dropna(subset=["p_nom_MW"]) if "p_nom_MW" in view.columns else pd.DataFrame()
        if not pnom.empty and pnom["p_nom_MW"].nunique() <= 2:
            st.caption(
                "El **p_nom total** casi no cambia entre épocas: la flota es la del nc "
                "(salvo cierre de carbón / Inversiones). Eso es coherente, no un fallo del gráfico."
            )

    if not out:
        st.info(
            "Aún no hay corrida HiGHS: por eso `objective_usd` aparece como «sin HiGHS» "
            "y no hay atlas. Cierre escenarios y pulse «Resolver todos los escenarios»."
        )
        return
    rootp = Path(out)
    st.caption(f"Última corrida: `{rootp}`")
    folders = sorted(rootp.glob("s*_e*"))
    if not folders:
        st.warning("La corrida no dejó carpetas sXX_eYY (ni mapas).")
        return
    st.subheader("Mapas de Colombia **por escenario**")
    st.caption(
        "Cada escenario tiene su propio atlas (demanda, generación, LMP, flujos). "
        "Fondo Grid2Poster. Naranja = demanda, verde = generación. No es el despacho XM."
    )
    by_sc: dict[str, list] = {}
    for epd in folders:
        title = epd.name
        sc_name = "escenario"
        meta = epd / "run_metadata_log.csv"
        if meta.exists():
            try:
                m = pd.read_csv(meta)
                if not m.empty:
                    sc_name = str(m.iloc[0].get("global_scenario") or sc_name)
                    title = f"{sc_name} · {m.iloc[0].get('name', epd.name)}"
            except Exception:
                pass
        by_sc.setdefault(sc_name, []).append((title, epd))
    for sc_name, items in by_sc.items():
        st.markdown(f"#### Escenario: {sc_name}")
        for title, epd in items:
            with st.expander(str(title), expanded=len(folders) <= 3):
                sc = epd / "system_costs.csv"
                if sc.exists():
                    try:
                        row = pd.read_csv(sc).iloc[0].to_dict()

                        def _f(val, default=0.0):
                            try:
                                if val is None or val == "":
                                    return default
                                return float(val)
                            except (TypeError, ValueError):
                                return default

                        obj = row.get("objective_usd")
                        obj_v = _f(obj)
                        gen_v = _f(row.get("generation_gwh"))
                        dem_v = _f(row.get("demand_gwh"))
                        obj_s = f"{obj_v:,.0f}" if obj_v else "— (HiGHS no devolvió objetivo)"
                        gen_s = f"{gen_v:.1f}" if gen_v else "— (sin despacho; vuelva a Resolver)"
                        _kpi_table(
                            [
                                ("Costo operativo", obj_s),
                                ("Demanda GWh (año)", f"{dem_v:.1f}" if dem_v else "—"),
                                ("Generación GWh (año)", gen_s),
                            ]
                        )
                    except Exception as exc:  # noqa: BLE001
                        st.warning(f"system_costs.csv ilegible: {exc}")
                board = epd / "atlas_4panel.png"
                if board.exists():
                    st.image(
                        str(board),
                        caption="Atlas 4 capas (demanda / generación / LMP / flujos)",
                        **stretch(),
                    )
                else:
                    st.caption("Sin atlas_4panel.png en esta época.")
                layer_files = [
                    "atlas_demanda.png",
                    "atlas_generacion.png",
                    "atlas_lmp.png",
                    "atlas_flujos.png",
                ]
                available = [f for f in layer_files if (epd / f).exists()]
                if available:
                    layer = st.selectbox(
                        "Ampliar una capa",
                        available,
                        format_func=lambda x: {
                            "atlas_demanda.png": "Demanda",
                            "atlas_generacion.png": "Generación",
                            "atlas_lmp.png": "LMP",
                            "atlas_flujos.png": "Flujos",
                        }.get(x, x),
                        key=f"layer-{epd.name}",
                    )
                    big = epd / layer
                    if big.exists():
                        st.image(
                            str(big),
                            caption=layer.replace("atlas_", "").replace(".png", ""),
                            **stretch(),
                        )
                legacy = epd / "colombia_map.png"
                if legacy.exists() and not board.exists():
                    st.image(str(legacy), caption="Mapa de red (legado)", **stretch())
                lmp = epd / "lmp.png"
                if lmp.exists() and not (epd / "atlas_lmp.png").exists():
                    st.image(str(lmp), caption="LMP legado", **stretch())


def _tab_gui_motor_b() -> None:
    st.warning("**Motor B (B1–B14) — en diseño / construcción.** Esta hoja no está activa todavía.")
    st.markdown(
        """
Las animaciones B1–B14 se están rediseñando. Mientras tanto use:

- **Resumen de escenarios** — costo operativo, GWh y mapas de Colombia (tras HiGHS).
- **Demanda de las épocas** — perfiles lun–dom tipo XM / SIN.
- **Generación de las épocas** — disponibilidad y despacho HiGHS.
- **Inversiones** — comparar un portafolio; los mapas de Colombia salen **después** de elegir y comparar.
"""
    )


def tab_gui() -> None:
    g_cfg, g_sum, g_dem, g_gen, g_mb = st.tabs(
        [
            "⚙️ Escenario y épocas",
            "📊 Resumen de escenarios",
            "📈 Demanda de las épocas",
            "⚡ Generación de las épocas",
            "⚡ Motor B (B1–B14)",
        ]
    )
    with g_cfg:
        _tab_gui_config()
    with g_sum:
        _tab_gui_scenario_summary()
    with g_dem:
        _tab_gui_epoch_demand()
    with g_gen:
        _tab_gui_epoch_generation()
    with g_mb:
        _tab_gui_motor_b()


def _blank_inv_rows(n: int = 5) -> pd.DataFrame:
    return pd.DataFrame(
        [{"tipo": "Solar", "zona": "Cesar", "zona_destino": "", "MW": 0.0} for _ in range(n)]
    )


def _add_inv_rows() -> None:
    extra = _blank_inv_rows(5)
    cur = st.session_state.get("inv_editor_widget")
    if cur is None:
        seed = st.session_state.get("inv_seed")
        st.session_state.inv_seed = pd.concat([seed, extra], ignore_index=True) if seed is not None else extra
        return
    df = pd.DataFrame(cur)
    if len(df) >= 40:
        return
    st.session_state.inv_seed = pd.concat([df, extra], ignore_index=True).head(40)


def tab_inversiones() -> None:
    st.markdown(
        "**Alternativas de inversión en el SIN — v3** (lógica UPME: ¿dónde pongo los MW?). "
        "Hasta **40 proyectos** (no 3). El portafolio se aplica a **todos los escenarios × épocas** "
        "de la cola GUI, no a un solo fondo. Redes: 7 nodos, 18 subáreas, **STN 144** y **OSM 251**."
    )
    st.caption(
        "Capex MUSD 2024 de orden de magnitud. No es el PGE. "
        "**Los mapas de Colombia salen abajo, solo después de Comparar** — muestran el efecto "
        "de *estas* inversiones (no el atlas genérico)."
    )
    import pypsa_col.investments as _inv

    INV_TYPES = _inv.INV_TYPES
    PACKAGES = _inv.PACKAGES
    ZONES_18 = _inv.ZONES_18
    MAX_CUSTOM_ITEMS = int(getattr(_inv, "MAX_CUSTOM_ITEMS", 40))
    compare_investments_multi = getattr(_inv, "compare_investments_multi", None)
    if compare_investments_multi is None:
        _one = _inv.compare_investments

        def compare_investments_multi(  # type: ignore[misc]
            root,
            selected,
            *,
            network_key="clustered-18",
            cases=None,
            solver="highs",
            custom_items=None,
        ):
            cases = list(cases or [{}])
            primary = None
            rows = []
            for i, ep in enumerate(cases):
                r = _one(
                    root,
                    selected,
                    network_key=network_key,
                    levers=ep or None,
                    solver=solver,
                    custom_items=custom_items,
                )
                k0, k1 = r["kpis_base"], r["kpis_inv"]
                rows.append(
                    {
                        "escenario": (ep or {}).get("global_scenario"),
                        "época": (ep or {}).get("name"),
                        "Δopex": r.get("opex_delta"),
                        "ΔENS_MWh": r.get("shed_delta"),
                        "ΔFNCE_GWh": (r.get("fnce_delta") or 0) / 1e3,
                        "base_status": r.get("base_status"),
                        "inv_status": r.get("inv_status"),
                    }
                )
                if primary is None:
                    primary = r
            return {
                "by_case": rows,
                "primary": primary,
                "n_cases": len(cases),
                "network": network_key,
                "applied": (primary or {}).get("applied") or [],
                "capex_musd": (primary or {}).get("capex_musd") or 0.0,
            }

    net = st.selectbox(
        "Red para el experimento",
        list(NETWORKS),
        format_func=lambda k: NETWORKS[k]["label"],
        key="inv_network",
    )
    zones = list(ZONES_18)
    if net == "dashboard-sin":
        from pypsa_col.dashboard_sin import ZONAS
        zones = [f"{k} · {v['label']}" for k, v in ZONAS.items()]

    st.subheader("1. Ubique alternativas (más de tres)")
    st.caption(
        f"Cada fila es un proyecto. Use **+** al pie de la tabla o el botón para 5 filas más "
        f"(máximo {MAX_CUSTOM_ITEMS}). Filas con MW = 0 se ignoran. "
        "Ejemplo: Eólica / Guajira / 500 MW · Refuerzo / Guajira → Cesar / 800 MW."
    )
    default = pd.DataFrame(
        [
            {"tipo": "Eólica", "zona": "Guajira", "zona_destino": "", "MW": 500.0},
            {"tipo": "Solar", "zona": "Cesar", "zona_destino": "", "MW": 400.0},
            {"tipo": "Solar", "zona": "Santander", "zona_destino": "", "MW": 300.0},
            {"tipo": "BESS 4 h", "zona": "Bogotá", "zona_destino": "", "MW": 200.0},
            {"tipo": "Refuerzo de red", "zona": "Guajira", "zona_destino": "Cesar", "MW": 800.0},
            {"tipo": "Refuerzo de red", "zona": "Atlántico", "zona_destino": "Bogotá", "MW": 600.0},
            {"tipo": "Gas de respaldo", "zona": "Bolívar", "zona_destino": "", "MW": 0.0},
            {"tipo": "Cierre carbón (zona)", "zona": "Cesar", "zona_destino": "", "MW": 0.0},
        ]
    )
    if "inv_seed" not in st.session_state:
        st.session_state.inv_seed = default
    st.button("Añadir 5 filas vacías", on_click=_add_inv_rows, key="btn_add_inv_rows")
    edited = st.data_editor(
        st.session_state.inv_seed,
        num_rows="dynamic",
        height=420,
        **stretch(),
        column_config={
            "tipo": st.column_config.SelectboxColumn("Tipo", options=list(INV_TYPES), required=True),
            "zona": st.column_config.SelectboxColumn("Zona / subárea", options=zones, required=True),
            "zona_destino": st.column_config.SelectboxColumn("Zona destino (solo refuerzo)", options=[""] + zones),
            "MW": st.column_config.NumberColumn("MW", min_value=0.0, step=50.0),
        },
        key="inv_editor_widget",
    )

    with st.expander("Recetas rápidas (opcional, se suman a la tabla si las marca)"):
        labels = {k: v["label"] for k, v in PACKAGES.items()}
        picked = st.multiselect(
            "Paquetes prearmados",
            list(PACKAGES),
            default=[],
            format_func=lambda k: labels[k],
            key="inv_pack",
        )
        st.dataframe(
            pd.DataFrame(
                [{"inversión": v["label"], "capex_MUSD": v["capex_musd"], "nota": v["note"]} for v in PACKAGES.values()]
            ),
            hide_index=True,
            **stretch(),
        )
    picked = st.session_state.get("inv_pack") or []

    study = _all_study_cases()
    st.subheader("2. Escenarios bajo estudio (cola GUI)")
    if study:
        labels = [c.get("_label") or f"{c.get('global_scenario')} · {c.get('name')}" for c in study]
        st.caption(
            "El mismo portafolio se resuelve **base vs con inversión** en cada casilla marcada. "
            "C1 y C3 (o las épocas de la cola) dejan de ser un solo fondo."
        )
        st.multiselect(
            "Aplicar el portafolio a",
            labels,
            default=labels,
            key="inv_cases",
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "caso": c.get("_label"),
                        "demanda": c.get("demand_scenario"),
                        "hidro": c.get("hydrology_scenario"),
                        "clima": c.get("climate_scenario"),
                        "años": c.get("representative_years"),
                        "meses": c.get("representative_months"),
                        "días": c.get("representative_days"),
                    }
                    for c in study
                ]
            ),
            hide_index=True,
            **stretch(),
        )
    else:
        st.info("No hay cola aún: se usará el escenario que esté en los selectores de la GUI.")
        st.session_state["inv_cases"] = []

    custom = edited.to_dict("records") if edited is not None and not edited.empty else []
    n_live = sum(1 for r in custom if float(r.get("MW") or 0) > 0 or str(r.get("tipo", "")).startswith("Cierre"))
    st.caption(f"Proyectos con MW > 0 (o cierre carbón): **{n_live}** (límite {MAX_CUSTOM_ITEMS}).")
    if st.button("Comparar operación base vs este portafolio", type="primary", key="btn_inv"):
        if n_live == 0 and not picked:
            st.warning("Añada al menos una fila con MW > 0 o una receta.")
        else:
            wanted = set(st.session_state.get("inv_cases") or [])
            cases = [c for c in study if (c.get("_label") in wanted)] if wanted else list(study)
            if not cases:
                try:
                    cases = [_settings_from_widgets()]
                    cases[0]["name"] = "GUI actual"
                    cases[0]["global_scenario"] = cases[0].get("global_scenario")
                except Exception:
                    cases = [{}]
            msg = (
                f"HiGHS · {len(cases)} escenario(s)×época × 2 (base e inversión) "
                f"en {NETWORKS[net]['label']}…"
            )
            with st.spinner(msg):
                try:
                    bundle = compare_investments_multi(
                        ROOT,
                        picked,
                        network_key=net,
                        cases=cases,
                        solver="highs",
                        custom_items=custom,
                    )
                    st.session_state["inv_bundle"] = bundle
                    st.session_state["inv_result"] = bundle.get("primary")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"No se pudo optimizar: {exc}")
                    return
    bundle = st.session_state.get("inv_bundle")
    result = (bundle or {}).get("primary") if bundle else st.session_state.get("inv_result")
    if bundle and bundle.get("by_case"):
        st.subheader("Efecto del portafolio en cada escenario bajo estudio")
        by = pd.DataFrame(bundle["by_case"])
        st.dataframe(by, hide_index=True, **stretch())
        plot_cols = [c for c in ("Δopex", "ΔENS_MWh", "ΔFNCE_GWh") if c in by.columns]
        if plot_cols and "escenario" in by.columns:
            idx = by.apply(lambda r: f"{r.get('escenario')} · {r.get('época')}", axis=1)
            chart = by[plot_cols].copy()
            chart.index = idx
            plot_series(chart, kind="bar", y_title="Δ (inversión − base)")
        st.caption(
            "Δopex < 0 = la operación se abarata en ese mundo. "
            "Un paquete puede ayudar en C3/Niña y no en C1/Niño: por eso se recorre la cola."
        )
    if not result:
        st.info("Pulse comparar para ver costo operativo, FNCE y energía no servida.")
        return
    k0, k1 = result["kpis_base"], result["kpis_inv"]
    st.subheader("Cómo leer este experimento")
    st.markdown(result.get("narrative") or "_Sin narrativa._")
    _kpi_table(
        [
            ("Capex paquete", f"{result['capex_musd']:,.0f} MUSD"),
            ("Costo op. con inv.", f"{k1['objective']:,.0f} (Δ {result['opex_delta']:+,.0f})"),
            ("ENS MWh", f"{k1['shed_mwh']:,.0f} (Δ {result['shed_delta']:+,.0f})"),
            ("FNCE GWh", f"{k1['fnce_mwh']/1e3:,.1f} (Δ {result['fnce_delta']/1e3:+,.1f})"),
            ("FNCE %", f"{k1['fnce_pct']:.1f} (Δ {k1['fnce_pct']-k0['fnce_pct']:+.1f} pp)"),
        ]
    )
    better = result["opex_delta"] < 0 or result["shed_delta"] < 0
    if better:
        st.success(
            f"Base **{result['base_status']}** · con inversión **{result['inv_status']}**. "
            "La operación mejora (menor costo y/o menos shedding)."
        )
    else:
        st.warning(
            f"Base **{result['base_status']}** · con inversión **{result['inv_status']}**. "
            "En esta ventana el portafolio no reduce costo ni shedding; revise zona o MW."
        )
    st.subheader("Base vs. con inversión (números anuales ponderados)")
    cmp_tbl = pd.DataFrame(
        {
            "base": [
                k0.get("objective", 0),
                k0.get("demand_mwh", 0) / 1e3,
                k0.get("shed_mwh", 0),
                k0.get("shed_pct", 0),
                k0.get("fnce_mwh", 0) / 1e3,
                k0.get("fnce_pct", 0),
                k0.get("hydro_mwh", 0) / 1e3,
                k0.get("coal_mwh", 0) / 1e3,
                k0.get("gas_mwh", 0) / 1e3,
            ],
            "con_inversion": [
                k1.get("objective", 0),
                k1.get("demand_mwh", 0) / 1e3,
                k1.get("shed_mwh", 0),
                k1.get("shed_pct", 0),
                k1.get("fnce_mwh", 0) / 1e3,
                k1.get("fnce_pct", 0),
                k1.get("hydro_mwh", 0) / 1e3,
                k1.get("coal_mwh", 0) / 1e3,
                k1.get("gas_mwh", 0) / 1e3,
            ],
        },
        index=[
            "Costo operativo (ud. modelo)",
            "Demanda GWh",
            "ENS MWh",
            "ENS % demanda",
            "FNCE GWh",
            "FNCE %",
            "Hidro GWh",
            "Carbón GWh",
            "Gas GWh",
        ],
    )
    cmp_tbl["delta"] = cmp_tbl["con_inversion"] - cmp_tbl["base"]
    st.dataframe(cmp_tbl.round(2), **stretch())
    mix = result["mix_mwh"].copy()
    mix.index = [NICE_NAME.get(i, i) for i in mix.index]
    dem = float(k1.get("demand_mwh") or 0) or 1.0
    mix["base_%dem"] = 100.0 * mix["base"] / dem
    mix["inv_%dem"] = 100.0 * mix["con_inversion"] / dem
    st.subheader("Energía por tecnología (MWh ponderados del año representativo)")
    plot_series(mix[["base", "con_inversion"]], kind="bar", y_title="MWh ponderados")
    st.dataframe(mix.round(1), **stretch())
    st.caption(
        "MWh = Σ P × snapshot_weightings. Un Δ negativo en carbón/gas y positivo en solar/eólica "
        "es el desplazamiento que busca FNCER. Si la demanda no cambia, el paquete no altera la carga, "
        "solo quién la sirve."
    )
    st.subheader("Qué se instaló (ubicación)")
    st.dataframe(
        pd.DataFrame(
            [
                {k: v for k, v in a.items() if k in {"label", "bus", "link", "p_nom", "delta_mw", "note", "units", "capex_musd"}}
                for a in result["applied"]
            ]
        ),
        hide_index=True,
        **stretch(),
    )
    st.subheader("Mapas de Colombia — modificaciones de este portafolio")
    st.caption(
        "Aparecen **solo después de Comparar**. Izquierda = despacho base. "
        "Derecha = con las inversiones (marcador = MW nuevo en esa subárea; trazo rojo = refuerzo). "
        "El mapa Δ es generación nodal con − sin el paquete. No es Grid2Poster de catálogo."
    )
    maps = result.get("maps") or {}
    if maps.get("error"):
        st.warning(f"No se pudieron dibujar los mapas: {maps['error']}")
    else:
        ba = maps.get("map_before_after.png")
        if ba and Path(ba).exists():
            st.image(ba, caption="Antes | Después (mismas escalas geográficas)", **stretch())
        cols_m = st.columns(2)
        left = maps.get("map_base_generacion.png")
        right = maps.get("map_inv_generacion.png")
        if left and Path(left).exists():
            cols_m[0].image(left, caption="Base", **stretch())
        if right and Path(right).exists():
            cols_m[1].image(right, caption="Con inversiones", **stretch())
        dlt = maps.get("map_delta_generacion.png")
        flw = maps.get("map_inv_flujos.png")
        if dlt and Path(dlt).exists():
            st.image(dlt, caption="Δ generación por subárea (verde más despacho, rojo menos)", **stretch())
        if flw and Path(flw).exists():
            st.image(flw, caption="Carga de corredores con el portafolio (rojo = refuerzo elegido)", **stretch())
        if result.get("map_dir"):
            st.caption(f"Archivos: `{result['map_dir']}`")
    with st.expander("Límites de esta lectura (Motor B)"):
        st.markdown(
            "- **No es GEP**: no hay variable de inversión ni anualidad de capex en el LP; "
            "el capex es una etiqueta ilustrativa.\n"
            "- **No es PET / N-1 AC** ni SDDP (valor del agua) ni ENFICC.\n"
            "- La demanda **sí crece** con el escenario C1–U3 y el año de la época de la GUI.\n"
            "- Repita el experimento bajo Niño y bajo C3 antes de una lista corta de proyectos."
        )


def tab_manual() -> None:
    path = ROOT / "docs" / "MANUAL_USUARIO.md"
    if path.exists():
        st.markdown(path.read_text(encoding="utf-8"))
    else:
        st.info("Falta docs/MANUAL_USUARIO.md")



# Same public API as dashboard-sin-nodal (servapibi.xm.com.co), last closed month D-1.
_XM_API = "https://servapibi.xm.com.co"
_XM_FEEDS = (
    ("listado", "ListadoRecursos", "Sistema", "lists"),
    ("cen", "CapEfecNeta", "Recurso", "daily"),
    ("gene", "Gene", "Recurso", "hourly"),
    ("dema", "DemaReal", "Sistema", "hourly"),
    ("gene_sis", "Gene", "Sistema", "hourly"),
    ("precio", "PrecBolsNaci", "Sistema", "hourly"),
)


def _xm_closed_window(days: int = 30) -> tuple[str, str]:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def _xm_post(kind: str, metric: str, entity: str, start: str, end: str) -> dict:
    if kind == "lists":
        body = {"MetricId": metric, "Entity": entity}
        url = f"{_XM_API}/lists"
    else:
        body = {
            "MetricId": metric,
            "Entity": entity,
            "StartDate": start,
            "EndDate": end,
            "Filter": [],
        }
        url = f"{_XM_API}/{kind}"
    resp = requests.post(url, json=body, timeout=8)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, dict) or "Items" not in payload:
        raise RuntimeError(f"XM {metric}/{entity}: respuesta inesperada")
    return payload


def _xm_melt(payload: dict, metric: str, entity: str, kind: str) -> pd.DataFrame:
    rows = []
    for item in payload.get("Items") or []:
        day = item.get("Date")
        entities = (
            item.get("HourlyEntities")
            or item.get("DailyEntities")
            or item.get("ListEntities")
            or item.get("ListsEntities")
            or []
        )
        for ent in entities:
            values = ent.get("Values", ent)
            if not isinstance(values, dict):
                continue
            code = str(
                next(
                    (values[k] for k in ("code", "Code", "Name", "name") if k in values),
                    ent.get("Id", entity),
                )
            )
            common = {
                "metric": metric,
                "entity": entity,
                "entity_code": code,
                "unit": "",
                "timezone": "America/Bogota",
            }
            if kind == "hourly":
                stamp0 = pd.Timestamp(str(day)[:10])
                for hour in range(1, 25):
                    key = f"Hour{hour:02d}"
                    if key not in values:
                        continue
                    rows.append(
                        {
                            **common,
                            "timestamp": stamp0 + pd.Timedelta(hours=hour - 1),
                            "value": pd.to_numeric(values[key], errors="coerce"),
                        }
                    )
            elif kind == "lists":
                rows.append({**common, "as_of": day, **values})
            else:
                val = values.get("Value", values.get("value"))
                rows.append(
                    {
                        **common,
                        "timestamp": pd.Timestamp(str(day)[:10]),
                        "value": pd.to_numeric(val, errors="coerce"),
                    }
                )
    return pd.DataFrame(rows)


def _load_metric_folder(folder: Path) -> dict:
    out = {}
    mapping = {
        "listado": "ListadoRecursos__Sistema.csv",
        "cen": "CapEfecNeta__Recurso.csv",
        "gene": "Gene__Recurso.csv",
        "dema": "DemaReal__Sistema.csv",
        "gene_sis": "Gene__Sistema.csv",
        "precio": "PrecBolsNaci__Sistema.csv",
    }
    for key, name in mapping.items():
        path = folder / name
        if not path.exists():
            continue
        df = pd.read_csv(path, dtype={"entity_code": str}, keep_default_na=False, na_values=[""])
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        out[key] = df
    return out


def _fetch_xm_last_month(dest: Path, days: int = 30) -> dict:
    """dashboard-sin-nodal convention: last `days` ending yesterday (D-1)."""
    start, end = _xm_closed_window(days)
    dest.mkdir(parents=True, exist_ok=True)
    notes = []
    saved = []
    for key, metric, entity, kind in _XM_FEEDS:
        try:
            payload = _xm_post(kind, metric, entity, start, end)
            df = _xm_melt(payload, metric, entity, kind)
            if df.empty:
                notes.append(f"{metric}/{entity}: vacío")
                continue
            df.to_csv(dest / f"{metric}__{entity}.csv", index=False)
            saved.append({"metric": metric, "entity": entity, "rows": int(len(df))})
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{metric}/{entity}: {exc}")
    meta = {
        "start": start,
        "end": end,
        "timezone": "America/Bogota",
        "days": days,
        "source": "XM SINERGOX live (servapibi.xm.com.co, D-1, dashboard-sin-nodal)",
        "datasets": saved,
        "notes": notes,
    }
    (dest / "window.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


@st.cache_data(ttl=6 * 3600, show_spinner="Descargando último mes XM (ventana D-1, 30 días)…")
def _xm_dashboard(nonce: int = 0):
    """Live last-month XM like dashboard-sin-nodal; fallback to bundled extract."""
    live_dir = ROOT / "data" / "streamlit" / "xm_last_month"
    bundle = ROOT / "data" / "streamlit" / "xm"
    meta: dict = {}
    # Never hit servapibi on first paint (proxy 502). Only when the user asks.
    need = nonce > 0
    if need:
        try:
            meta = _fetch_xm_last_month(live_dir, days=30)
        except Exception as exc:  # noqa: BLE001
            meta = {
                "source": "fallback bundle ene-2024",
                "error": str(exc),
                "start": XM_BUNDLE_START,
                "end": XM_BUNDLE_END,
            }
    elif (live_dir / "window.json").exists():
        meta = json.loads((live_dir / "window.json").read_text(encoding="utf-8"))
    folder = live_dir if (live_dir / "DemaReal__Sistema.csv").exists() else bundle
    if folder == bundle:
        meta.setdefault("source", "extracto empaquetado 2023-12-31 → 2024-01-02")
        meta.setdefault("start", XM_BUNDLE_START)
        meta.setdefault("end", XM_BUNDLE_END)
    tables = _load_metric_folder(folder)
    from pypsa_col.xm import drop_incomplete_demand_tail

    meta = drop_incomplete_demand_tail(tables, meta)
    if "dema" in tables and not tables["dema"].empty:
        idx = pd.DatetimeIndex(
            sorted(pd.to_datetime(tables["dema"]["timestamp"]).unique()), name="snapshot"
        )
    else:
        idx = pd.DatetimeIndex([], name="snapshot")
    meta["folder"] = str(folder)
    meta["n_hours"] = int(len(idx))
    return tables, idx, meta


def _dashboard_payload():
    return _xm_dashboard(nonce=int(st.session_state.get("xm_nonce", 0)))


def tab_generacion() -> None:
    st.markdown(
        "**⚡ Generación XM — último mes cerrado** (ventana D-1 de 30 días, America/Bogota). "
        "No es el despacho de las épocas de la GUI; es el mix observado del SIN en el último "
        "mes que XM ya cerró. Estilo dashboard-sin-nodal: catálogo, CEN y energía de esa ventana."
    )
    c_a, c_b = st.columns([3, 1])
    with c_b:
        if st.button("Actualizar último mes XM", key="btn_xm_gen"):
            st.session_state.xm_nonce = int(st.session_state.get("xm_nonce", 0)) + 1
            _xm_dashboard.clear()
            st.rerun()
    try:
        tables, idx, meta = _dashboard_payload()
        _data_window_banner(meta)
        from pypsa_col.dashboard_sin import assemble_plants

        plants = assemble_plants(tables, idx if len(idx) else tables["cen"].index[:1])
    except Exception as exc:  # noqa: BLE001
        st.error(f"No se pudieron leer las tablas XM: {exc}")
        return
    _kpi_table(
        [
            ("Plantas XM", f"{len(plants):,}"),
            ("CEN", f"{plants['cen_mw'].sum():,.0f} MW"),
            ("Energía ventana", f"{plants['gene_mwh'].sum()/1000:,.1f} GWh"),
            ("Tecnologías", str(plants["carrier"].nunique())),
        ]
    )
    mix = plants.groupby("carrier")["cen_mw"].sum().sort_values(ascending=False)
    plot_series(mix.rename(index=lambda x: NICE_NAME.get(x, x)), kind="bar", y_title="CEN MW")
    zona = st.multiselect("Filtrar zona", sorted(plants["zona"].dropna().unique()), default=[])
    car = st.multiselect("Filtrar tecnología", sorted(plants["carrier"].dropna().unique()), default=[])
    view = plants
    if zona:
        view = view[view["zona"].isin(zona)]
    if car:
        view = view[view["carrier"].isin(car)]
    show_cols = [c for c in ["Nombre_Planta", "zona", "carrier", "cen_mw", "gene_mwh", "cf"] if c in view.columns]
    if not show_cols:
        show_cols = list(view.columns)[:8]
    st.dataframe(view[show_cols], **stretch(), hide_index=True)


def tab_demanda() -> None:
    st.markdown(
        "**📈 Demanda XM — último mes cerrado** (DemaReal nacional, ventana D-1 de 30 días). "
        "No es el escenario de demanda de las épocas de la GUI. Se parte con `PESO_DEMANDA` "
        "del dashboard-sin-nodal (subregiones declaradas)."
    )
    try:
        tables, idx, meta = _dashboard_payload()
        _data_window_banner(meta)
        from pypsa_col.dashboard_sin import PESO_DEMANDA, demand_by_zone

        dem = demand_by_zone(tables["dema"], idx)
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
        return
    plot_series(dem, kind="line", y_title="MW", x_title="Tiempo (último mes XM)")
    st.caption(
        "MW por subregión declarada (no son zonas oficiales XM/UPME). "
        "Los últimos días de XM DemaReal a veces llegan preliminares (~¼ del SIN); "
        "esa cola se descarta si no cuadra con Gene del sistema. "
        "Clic en la leyenda para ocultar una zona. Este mes es el **benchmark** de forma horaria "
        "que usa la GUI (pico nocturno, valle madrugada, domingo más bajo)."
    )
    plot_series(pd.Series(PESO_DEMANDA, name="peso"), kind="bar", y_title="Peso")
    tot = dem.sum().sum() / 1000.0
    _kpi_table([("Energía ventana (último mes XM)", f"{tot:,.2f} GWh")])
    st.dataframe(dem, **stretch())


def tab_explorador() -> None:
    st.markdown("Pestaña **🏭 Explorador de planta** (dashboard-sin-nodal).")
    try:
        tables, idx, meta = _dashboard_payload()
        _data_window_banner(meta)
        from pypsa_col.dashboard_sin import assemble_plants

        plants = assemble_plants(tables, idx)
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
        return
    names = plants["Nombre_Planta"].astype(str).tolist() if "Nombre_Planta" in plants.columns else plants.index.astype(str).tolist()
    pick = st.selectbox("Planta", names)
    row = plants[plants["Nombre_Planta"].astype(str) == pick].iloc[0] if "Nombre_Planta" in plants.columns else plants.iloc[0]
    _kpi_table(
        [
            ("CEN MW", f"{float(row.get('cen_mw', 0)):.1f}"),
            ("Energía MWh", f"{float(row.get('gene_mwh', 0)):.0f}"),
            ("CF", f"{float(row.get('cf', 0)):.2f}"),
        ]
    )
    st.json(
        {
            k: (None if pd.isna(v) else (v.item() if hasattr(v, "item") else v))
            for k, v in row.items()
            if k in {"zona", "carrier", "Codigo_Planta", "cen_mw", "gene_mwh", "cf"}
        }
    )
    gene = tables["gene"].copy()
    code = str(row.get("Codigo_Planta", ""))
    gene["entity_code"] = gene["entity_code"].astype(str)
    sub = gene[gene["entity_code"] == code]
    if sub.empty:
        st.info("Sin serie Gene para este recurso en la ventana.")
        return
    sub = sub.copy()
    sub["mw"] = sub["value"] / 1000.0
    plot_series(sub.set_index("timestamp")["mw"], kind="line", y_title="MW")


def tab_red() -> None:
    st.markdown(
        "**Tres modelos** (tesis Moreno / PARATEC + dashboard-SIN) y **Grid2Poster** "
        "(OSM Colombia, adaptación colombiacongestionV2) como fondo de los atlas "
        "de demanda, generación, LMP y flujos."
    )
    board = ROOT / "data" / "streamlit" / "figures" / "atlas_4panel.png"
    if board.exists():
        st.image(
            str(board),
            caption="Atlas 18 subáreas · fondo Grid2Poster OSM · naranja demanda / verde generación / LMP / carga de corredores.",
            **stretch(),
        )
    catalog = ROOT / "data" / "streamlit" / "networks" / "three_models.json"
    if catalog.exists():
        meta = json.loads(catalog.read_text(encoding="utf-8"))
        stn = meta.get("stn", {})
        ext = stn.get("this_extract", {})
        reported = stn.get("thesis_reported", {})
        c18 = meta.get("clustered18", {})
        st.subheader("El Modelo — STN físico")
        st.caption(
            f"Extracto PARATEC publicado: **{ext.get('buses')} buses, {ext.get('lines')} líneas, "
            f"{ext.get('transformers')} transformadores**. "
            f"La tesis de maestría 2026 reporta **{reported.get('buses')}/{reported.get('lines')}/"
            f"{reported.get('transformers')}** sobre un PARATEC posterior (no está en el repo público). "
            "Buses diferenciados por 220/230/500 kV; transformadores en subestaciones multi-kV; "
            "capacidad N-1 = MVA instalado − circuito mayor. KVL (líneas PyPSA)."
        )
        st.subheader("18 subáreas operativas")
        st.caption(
            f"Agregación §4: **{c18.get('n_subareas')} nodos**, **{c18.get('links')} enlaces** "
            "bidireccionales (`p_min_pu = -1`) con N-1 y costo marginal ∝ distancia. KCL (links)."
        )
        st.subheader("Modelo pequeño — 7 nodos")
        st.caption(
            "Hubs declarados de dashboard-sin-nodal (La Guajira–Cesar–Magdalena, Caribe, Nordeste, "
            "Centro, Occidente, Sur, Orinoquía). No son subáreas oficiales XM."
        )
    buses_csv = ROOT / "data" / "tesis_stn" / "stn_buses.csv"
    if buses_csv.exists():
        bdf = pd.read_csv(buses_csv)
        if {"x", "y"}.issubset(bdf.columns):
            show = bdf.rename(columns={"y": "lat", "x": "lon"})
            cols = [c for c in ("name", "station", "subarea", "v_nom", "lat", "lon") if c in show.columns]
            st.dataframe(show[cols] if cols else show.head(), hide_index=True, **stretch())
            st.map(show.dropna(subset=["lat", "lon"]), latitude="lat", longitude="lon", size=40)
    st.divider()
    st.markdown("**Grid2Poster** (OSM Colombia, adaptación colombiacongestionV2).")
    poster = ROOT / "data" / "streamlit" / "figures" / "grid2poster_colombia.png"
    alt = ROOT / "results" / "demo" / "grid2poster.png"
    shown = poster if poster.exists() else alt
    if shown.exists():
        st.image(
            str(shown),
            caption="Grid2Poster · Colombia · tema electric_midnight · geometría OSM (ODbL) · no es un diagrama unifilar oficial.",
            **stretch(),
        )
    else:
        st.info("No hay PNG de Grid2Poster. Pulse renderizar si el source está clonado.")
    if st.button("Renderizar Grid2Poster ahora"):
        try:
            from pypsa_col.io import load_config
            from pypsa_col.poster import render_grid2poster

            cfg = load_config(ROOT / "config" / "demo.yaml")
            dest = ROOT / "data" / "streamlit" / "figures"
            dest.mkdir(parents=True, exist_ok=True)
            render_grid2poster(ROOT, cfg, dest)
            produced = dest / "grid2poster.png"
            if produced.exists():
                produced.replace(poster)
            st.success("Grid2Poster actualizado.")
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.warning(f"No se pudo renderizar (¿falta external/colombiacongestionV2?): {exc}")
    st.divider()
    from pypsa_col.dashboard_sin import RAMAS, ZONAS

    z = pd.DataFrame(
        [{"zona": k, "label": v["label"], "lon": v["x"], "lat": v["y"]} for k, v in ZONAS.items()]
    )
    st.subheader("7 subregiones dashboard-SIN (declaradas, no oficiales)")
    st.dataframe(z, hide_index=True, **stretch())
    r = pd.DataFrame(RAMAS, columns=["from", "to", "NTC_MW", "nombre"])
    st.dataframe(r, hide_index=True, **stretch())
    st.map(z.rename(columns={"lat": "lat", "lon": "lon"}), latitude="lat", longitude="lon", size=200)
    st.caption("Advertencia: subregiones y NTC son supuestos del tablero, no un registro PARATEC/UPME.")
    m = ROOT / "data" / "streamlit" / "figures" / "sin_network.png"
    if m.exists():
        st.image(str(m), caption="Malla OSM PyPSA (naranja demanda / verde generación)")


def tab_resultados() -> None:
    st.markdown("CSV estilo PyPSA-CL (`generation_results`, `system_costs`, …) de la última corrida HiGHS.")
    st.caption("Esta hoja no es XM del último mes: son salidas del solver de la pestaña GUI.")
    out = st.session_state.last_outdir
    if not out:
        st.info("Todavía no hay corrida en esta sesión. Use la pestaña GUI → Run all scenarios.")
        bundled = ROOT / "results" / "osm-interactive"
        if (bundled / "summary.json").exists():
            st.json(json.loads((bundled / "summary.json").read_text()))
        return
    p = Path(out)
    st.code(str(p))
    costs = p / "system_costs.csv"
    if costs.exists():
        st.dataframe(pd.read_csv(costs), **stretch())
    for ep in sorted(p.glob("s*_e*")):
        st.subheader(ep.name)
        for csv in [
            "system_costs.csv",
            "installed_capacity.csv",
            "energy_balance_gwh.csv",
            "run_metadata_log.csv",
            "nodal_marginal_prices.csv",
        ]:
            f = ep / csv
            if f.exists():
                with st.expander(csv):
                    st.dataframe(pd.read_csv(f), **stretch())
        gen = ep / "generation_results.csv"
        if gen.exists():
            st.download_button(
                f"Descargar {ep.name}/generation_results.csv",
                gen.read_bytes(),
                file_name=f"{ep.name}_generation_results.csv",
                mime="text/csv",
                key=f"dl-{ep.name}",
            )


def tab_metodo() -> None:
    st.markdown(
        """
**PyPSA-col** reutiliza [colombiacongestionV2](https://github.com/srriverar/colombiacongestionV2)
y las reglas declaradas de [dashboard-sin-nodal](https://github.com/srriverar/dashboard-sin-nodal).
La GUI sigue [PyPSA-CL GUI.py](https://github.com/paredes-vergara/PyPSA-CL/blob/main/src/GUI.py).
El Modelo STN y las 18 subáreas siguen la tesis de Juan Moreno
([Tesis_RedTransmisionColombia](https://github.com/JuanMoreno2000/Tesis_RedTransmisionColombia)
+ tesis de maestría 2026). [pypsa-colombia](https://github.com/pypsa-meets-earth/pypsa-colombia)
es un flujo OSM/Snakemake Earth: **no** es el STN de 147 nodos.

| Palanca | Efecto en el LP |
| --- | --- |
| Demanda Baja/Media/Alta | escala `loads_t.p_set` |
| Hidrología seca / media / húmeda | escala `p_max_pu` hidro |
| Niño / Niña | ajusta hidrología |
| Precio combustible Alto/Medio/Bajo | escala `marginal_cost` térmico |
| Cierre de carbón | `p_nom` carbón = 0 |
| Capex generación/almacenamiento | se registra en el JSON (GEP completo tipo PELP aún no) |

Solver por defecto: **HiGHS**. Las épocas usan los snapshots ya contenidos en `network.nc`
como periodo representativo.

```bash
streamlit run app.py
python src/main.py --scenario-json pypsa-col-scenario.json
PYTHONPATH=src python -m pypsa_col gui
snakemake -s workflow/Snakefile.osm.smk --cores 2
```
"""
    )
    from matplotlib.colors import to_hex

    palette = pd.DataFrame(
        [
            {
                "carrier": NICE_NAME.get(k, k),
                "workshop": v,
                "hex": to_hex(v),
            }
            for k, v in WORKSHOP_COLORS.items()
            if k in STACK_ORDER
        ]
    )
    st.dataframe(palette, hide_index=True, **stretch())
    st.color_picker("Workshop Gas (hex)", to_hex(WORKSHOP_COLORS["Gas"]), disabled=True)


def main() -> None:
    patch_linopy_pandas3()
    _css()
    _init_state()
    logo = ROOT / "data" / "streamlit" / "figures" / "logo.png"
    cols = st.columns([1, 4])
    with cols[0]:
        if logo.exists():
            st.image(str(logo), **stretch())
    with cols[1]:
        st.title("PyPSA-col v3 — Long-term Power Systems Planning in Colombia")
        st.caption(
            "SIN · XM DemaReal / CEN · malla OSM · HiGHS  ·  GUI fiel a PyPSA-CL  ·  "
            "esta app **sí corre el solver** (no es el sitio estático de Netlify).  "
            "Hojas XM (Generación, Demanda, Explorador): **último mes cerrado D-1** "
            "(como dashboard-sin-nodal). Tres modelos: El Modelo STN, 18 subáreas, 7 nodos. Red SIN: Grid2Poster OSM."
        )

    if on_streamlit_cloud():
        st.info(
            "Streamlit Community Cloud tiene ~1 GB de RAM. "
            "En **El Modelo STN** use 1 año × 1 mes × 7 días (o 24 h). "
            "2 épocas × 5 años × 6 meses × 7 días genera un LP de ~1 millón de filas: "
            "el primer HiGHS puede terminar y el segundo tumba el contenedor. "
            "Para estudios grandes: red de **18 subáreas** o **7 nodos**, o corra en su PC."
        )

    t_gui, t_inv, t_gen, t_dem, t_exp, t_red, t_res, t_man, t_doc = st.tabs(
        [
            "🎛️ GUI (PyPSA-COL)",
            "🏗️ Inversiones",
            "⚡ Generación (último mes)",
            "📈 Demanda (último mes)",
            "🏭 Explorador de planta",
            "🔌 Red SIN",
            "📂 Resultados HiGHS",
            "📖 Manual de usuario",
            "ℹ️ Método",
        ]
    )
    def _safe(name: str, fn) -> None:
        try:
            fn()
        except ModuleNotFoundError as exc:
            st.error(
                f"Falta un paquete de Python para **{name}**: `{exc}`. "
                "En el entorno de la app instale `pypsa`, `highspy` y `streamlit`. "
                "Las demás pestañas siguen disponibles."
            )
        except Exception as exc:  # noqa: BLE001
            st.exception(exc)

    with t_gui:
        _safe("GUI (Motor B)", tab_gui)
    with t_inv:
        _safe("Inversiones", tab_inversiones)
    with t_gen:
        _safe("Generación XM", tab_generacion)
    with t_dem:
        _safe("Demanda XM", tab_demanda)
    with t_exp:
        _safe("Explorador de planta", tab_explorador)
    with t_red:
        _safe("Red SIN", tab_red)
    with t_res:
        _safe("Resultados HiGHS", tab_resultados)
    with t_man:
        _safe("Manual", tab_manual)
    with t_doc:
        _safe("Método", tab_metodo)


if __name__ == "__main__":
    main()
