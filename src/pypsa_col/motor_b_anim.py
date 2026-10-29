"""Motor B animations (expansion & operation). 🎨 illustrative · 📊 study-case data.

Particles/flows are pedagogical unless tied to n.lines_t / n.links_t after HiGHS.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from pypsa_col.plotting import NICE_NAME
from pypsa_col.st_compat import stretch
from pypsa_col.mde.animations import TAG_CMP, TAG_DATOS, TAG_ILUST, inject

# Prefix for Streamlit widget keys — Streamlit runs every tab body, so keys
# must stay unique even if B7 is mounted once.
_NS = "all"


def _wk(name: str, extra: str = "") -> str:
    return f"mb-{_NS}-{name}-{extra}"


def _empty_s() -> pd.Series:
    return pd.Series(dtype="float64")


def _pnl(n, component: str, attr: str) -> pd.DataFrame:
    try:
        pnl = getattr(n, f"{component}_t", None)
        if pnl is None:
            return pd.DataFrame()
        df = getattr(pnl, attr, None)
        if df is None or getattr(df, "empty", True):
            return pd.DataFrame()
        return df
    except (TypeError, ValueError, KeyError, AttributeError):
        return pd.DataFrame()

CAR = {
    "Solar": "#F5D76E",
    "Wind Onshore": "#1ABC9C",
    "Storage Hydro": "#5DADE2",
    "Run of River": "#3498DB",
    "Hydro": "#3498DB",
    "Gas": "#2E6DA4",
    "Hard Coal": "#4A4A4A",
    "Oil": "#922B21",
    "load shedding": "#C0392B",
    "Pumped Hydro": "#8E44AD",
}


def _tag(kind: str, escenario: str, epoca: str, extra: str = "") -> None:
    t = {"ilust": TAG_ILUST, "datos": TAG_DATOS, "cmp": TAG_CMP}.get(kind, TAG_DATOS)
    st.markdown(
        f"{t} · escenario **{escenario}** · época **{epoca}** · {extra}",
        unsafe_allow_html=True,
    )


def collect_cases(epochs: list, preview_fn, cap: int = 4) -> list[dict]:
    """Load up to `cap` study networks (levers applied, not always optimized)."""
    out = []
    for i, ep in enumerate((epochs or [])[:cap]):
        lab = ep.get("_label") or ep.get("name") or f"época-{i}"
        try:
            n, key = preview_fn(ep)
        except Exception as exc:  # noqa: BLE001
            out.append(
                {
                    "ep": ep,
                    "error": str(exc),
                    "escenario": ep.get("global_scenario") or "—",
                    "epoca": ep.get("name") or "—",
                    "label": lab,
                }
            )
            continue
        p_set = _pnl(n, "loads", "p_set")
        load = p_set.sum(axis=1) if not p_set.empty else _empty_s()
        gens = n.generators[n.generators.carrier != "load shedding"] if len(n.generators) else n.generators
        cap_mw = gens.groupby("carrier")["p_nom"].sum() if len(gens) else _empty_s()
        pu = _pnl(n, "generators", "p_max_pu")
        avail = pd.DataFrame()
        if not pu.empty and len(gens):
            cols = pu.columns.intersection(gens.index)
            if len(cols):
                avail = pu[cols].mul(gens.reindex(cols)["p_nom"], axis=1)
                avail = avail.T.groupby(gens.loc[cols, "carrier"]).sum().T
        p_disp = _pnl(n, "generators", "p")
        dispatched = pd.DataFrame()
        if not p_disp.empty and len(n.generators):
            dispatched = p_disp.T.groupby(n.generators.carrier).sum().T
        shed = 0.0
        if not dispatched.empty and "load shedding" in dispatched.columns:
            shed = float(dispatched["load shedding"].sum())
        if "objective" in getattr(n, "snapshot_weightings", pd.DataFrame()).columns:
            w = n.snapshot_weightings["objective"]
        else:
            w = pd.Series(1.0, index=n.snapshots, dtype="float64")
        demand_mwh = float((load.reindex(w.index).fillna(0) * w).sum()) if len(load) else 0.0
        out.append(
            {
                "ep": ep,
                "n": n,
                "key": key,
                "key_id": f"{i}-{ep.get('global_scenario')}-{ep.get('name')}",
                "label": lab,
                "escenario": ep.get("global_scenario") or "—",
                "epoca": ep.get("name") or "—",
                "year": str(ep.get("start_date") or "")[:4],
                "load": load,
                "cap_mw": cap_mw,
                "avail": avail,
                "dispatch": dispatched,
                "shed_mwh": shed,
                "demand_mwh": demand_mwh,
                "solved": bool(not p_disp.empty),
            }
        )
    return out


def _pick(cases: list[dict], key: str) -> dict | None:
    ok = [c for c in cases if "n" in c]
    if not ok:
        return None
    labels = [c["label"] for c in ok]
    lab = st.selectbox("Caso (escenario × época bajo estudio)", labels, key=_wk("case", key))
    return next(c for c in ok if c["label"] == lab)


def b1_panorama(c: dict) -> None:
    st.markdown("**B1. ¿Cómo se compone el sistema y cómo evoluciona?**")
    _tag("ilust", c["escenario"], c["epoca"], "flujos = partículas pedagógicas, no el AC")
    inject(
        f"""
        {TAG_ILUST}
        <svg viewBox="0 0 640 220" width="100%" height="220">
          <text x="80" y="24" text-anchor="middle" font-size="12">Fuentes</text>
          <circle cx="40" cy="70" r="16" fill="#5DADE2"/><text x="40" y="100" text-anchor="middle" font-size="10">hidro</text>
          <rect x="70" y="54" width="28" height="28" fill="#4A4A4A"/><text x="84" y="100" text-anchor="middle" font-size="10">térmica</text>
          <polygon points="130,54 146,82 114,82" fill="#F5D76E"/><text x="130" y="100" text-anchor="middle" font-size="10">solar</text>
          <polygon points="170,70 186,54 202,70 186,86" fill="#1ABC9C"/><text x="186" y="100" text-anchor="middle" font-size="10">eólica</text>
          <rect x="220" y="54" width="20" height="28" fill="#8E44AD"/><text x="230" y="100" text-anchor="middle" font-size="10">BESS</text>
          <line class="flow-line" x1="250" y1="70" x2="340" y2="70" stroke="#b85716" stroke-width="3"/>
          <rect x="340" y="40" width="90" height="60" fill="#f7f4ee" stroke="#b85716"/>
          <text x="385" y="75" text-anchor="middle" font-size="11">STN / subáreas</text>
          <line class="flow-line" x1="430" y1="70" x2="500" y2="70" stroke="#b85716" stroke-width="3"/>
          <rect x="500" y="30" width="120" height="36" fill="#fff8e8" stroke="#b85716"/>
          <text x="560" y="52" text-anchor="middle" font-size="11">Ciudades / industria</text>
          <rect x="500" y="80" width="120" height="36" fill="#eee" stroke="#888" stroke-dasharray="4 3"/>
          <text x="560" y="102" text-anchor="middle" font-size="11">ZNI (distinta del SIN)</text>
        </svg>
        <p style="font-size:13px">ZNI sombreada a propósito: no es el mismo modelo que el SIN. Alterne esquema 🎨 vs datos 📊 abajo.</p>
        """,
        250,
    )
    modo = st.radio(
        "Vista",
        ["Esquema ilustrativo", "Datos del caso"],
        horizontal=True,
        key=_wk("b1m", c.get("key_id") or c["label"]),
    )
    if modo.startswith("Datos"):
        _tag("datos", c["escenario"], c["epoca"], f"red {c['key']} · MW instalados (p_nom), no GWh")
        cap = c["cap_mw"].rename(index=lambda x: NICE_NAME.get(x, x))
        st.bar_chart(cap)
        st.caption(
            "Una tecnología puede tener mucha **capacidad (MW)** y otra participación en **energía (MWh)** "
            "según disponibilidad. El despacho 📊 aparece cuando HiGHS ya corrió."
        )
        if c["solved"] and not c["dispatch"].empty:
            e = c["dispatch"].clip(lower=0).sum().rename(index=lambda x: NICE_NAME.get(x, x))
            st.bar_chart(e)
            st.caption("GWh de la ventana = Σ P × peso; no es tarifa.")
        else:
            st.info("Aún no hay despacho. Pulse Resolver en esta GUI. No se anima una expansión «óptima» sin ejecución.")


def b2_red(c: dict) -> None:
    st.markdown("**B2. Red y nodos**")
    n = c["n"]
    _tag("datos", c["escenario"], c["epoca"], f"{len(n.buses)} buses · líneas {len(n.lines)} · enlaces {len(n.links)}")
    st.warning("Cambiar esta vista **no** aumenta la resolución del LP. Si resolvió 18 subáreas, no hay resultados de 147 nodos.")
    res = st.radio(
        "Resolución mostrada (visualización)",
        ["La del caso (modelo calculado)", "Esquema nacional agregado 🎨"],
        key=_wk("b2r", c.get("key_id") or c["label"]),
    )
    buses = n.buses.copy()
    buses["demanda_MW"] = n.loads.groupby("bus")["p_set"].sum() if "p_set" in n.loads.columns else 0
    if not n.loads_t.p_set.empty:
        mean_load = n.loads_t.p_set.mean()
        if "bus" in n.loads.columns:
            buses["demanda_media_MW"] = mean_load.groupby(n.loads.bus).sum()
    st.dataframe(buses.reset_index().head(40), hide_index=True, **stretch())
    if res.startswith("Esquema"):
        st.caption("🎨 Agregado pedagógico. Grosor ≠ flujo real.")
    if not n.lines.empty:
        L = n.lines[["bus0", "bus1", "s_nom"]].copy() if "s_nom" in n.lines.columns else n.lines[["bus0", "bus1"]].copy()
        st.markdown("Líneas: capacidad `s_nom`. Color de congestión solo si hay `lines_t.p0` post-HiGHS.")
        st.dataframe(L.head(20), **stretch())
    if not n.links.empty:
        st.markdown("Enlaces 18-subáreas (transporte). Grosor = capacidad; color = utilización **si** hay flujo resuelto.")
        cols = [c for c in ("bus0", "bus1", "p_nom") if c in n.links.columns]
        st.dataframe(n.links[cols].head(25), **stretch())
        if hasattr(n, "links_t") and not n.links_t.p0.empty:
            util = n.links_t.p0.abs().mean() / n.links.p_nom.replace(0, pd.NA)
            st.bar_chart(util.dropna().head(18))
            st.caption("📊 Utilización media |p0|/p_nom. Rojo visual ≠ incumplimiento N-1 real.")
        else:
            st.caption("Sin flujo horario: no se dibujan flechas de dirección física.")


def b3_generacion(c: dict) -> None:
    st.markdown("**B3. Generación: ¿qué abastece y cuándo?**")
    _tag("datos", c["escenario"], c["epoca"], "existente = p_nom del nc; no hay GEP endógeno")
    cap = c["cap_mw"].rename(index=lambda x: NICE_NAME.get(x, x))
    st.bar_chart(cap)
    st.caption("Sólido = existente en el caso. No hay barra «aprobada». Candidato de Inversiones ≠ autorización UPME.")
    if not c["avail"].empty:
        a = c["avail"].rename(columns=lambda x: NICE_NAME.get(x, x))
        st.markdown("Disponibilidad (p_nom × p_max_pu) 📊 — no es vertimiento por congestión.")
        st.area_chart(a.reset_index(drop=True))
        if c["solved"] and not c["dispatch"].empty:
            d = c["dispatch"].reindex(columns=c["avail"].columns).fillna(0)
            unused = (c["avail"] - d).clip(lower=0)
            st.markdown("Potencial − generación (definición del modelo). **No** todo es vertimiento por red.")
            st.area_chart(unused.rename(columns=lambda x: NICE_NAME.get(x, x)).reset_index(drop=True))


def b4_hidro(c: dict) -> None:
    st.markdown("**B4. Hidrología y embalses**")
    st.warning(
        "Este LP **no** es SDDP. Altura de agua = **simbólica** 🎨 a partir de p_max_pu hidro "
        "(aportes relativos). No hay volumen de embalse. Conocimiento perfecto de la trayectoria de snapshots; "
        "una animación **no** demuestra operación estocástica."
    )
    _tag("ilust", c["escenario"], c["epoca"], f"clima {c['ep'].get('climate_scenario')} · hidro {c['ep'].get('hydrology_scenario')}")
    hydro_cols = [col for col in c["avail"].columns if any(k in str(col) for k in ("Hydro", "hydro", "River"))]
    series = c["avail"][hydro_cols].sum(axis=1) if hydro_cols else _empty_s()
    if series.empty:
        st.info("Sin p_max_pu hidro en este nc.")
        return
    mx = float(series.max()) or 1.0
    frac = float(series.mean() / mx)
    h = 20 + 90 * frac
    inject(
        f"""
        {TAG_ILUST}
        <svg viewBox="0 0 260 160" width="260" height="160">
          <polygon points="30,20 230,20 210,140 50,140" fill="#dfe6e9" stroke="#2c3e50"/>
          <rect x="50" y="{140-h}" width="160" height="{h}" fill="#5DADE2" opacity="0.85"/>
          <text x="130" y="16" text-anchor="middle" font-size="11">nivel simbólico {frac*100:.0f}% del p_max medio</text>
        </svg>
        """,
        180,
    )
    st.line_chart(series.reset_index(drop=True).rename("MW_disponibles_hidro"))
    inject(
        f"""
        {TAG_ILUST}
        <div class="mde-eq">
          <div class="step">Aportes (p_max_pu)</div><div class="op">↓</div>
          <div class="step">Embalse superior 🎨</div><div class="op">↓</div>
          <div class="step">Central</div><div class="op">↓</div>
          <div class="step">Embalse inferior 🎨</div>
        </div>
        <p>Encadenamiento pedagógico. Usos no energéticos no están en el LP.</p>
        """,
        320,
    )
    st.markdown("**Sequía 🔄** — compare Niño vs Neutral eligiendo dos épocas en la cola (hidrología distinta), no un percentil.")


def b5_vre(c: dict) -> None:
    st.markdown("**B5. Solar y eólica**")
    _tag("datos", c["escenario"], c["epoca"], "p_max_pu del caso; el sol ☀️ es decorativo")
    load = c["load"].reset_index(drop=True).rename("demanda_MW")
    a = c["avail"].rename(columns=lambda x: NICE_NAME.get(x, x))
    solar = a["Solar"] if "Solar" in a.columns else pd.Series(0, index=a.index)
    wind = a["Eólica"] if "Eólica" in a.columns else (a["Wind Onshore"] if "Wind Onshore" in a.columns else pd.Series(0, index=a.index))
    df = pd.DataFrame(
        {
            "demanda_MW": load.values[: len(a)] if len(load) else 0,
            "solar_disp_MW": solar.reset_index(drop=True),
            "eolica_disp_MW": wind.reset_index(drop=True) if hasattr(wind, "reset_index") else wind,
        }
    )
    st.line_chart(df)
    st.caption(
        "Complementariedad **no** es una propiedad constante: depende de región, hora, año climático y correlación. "
        "Flechas de viento ≠ meteorología observada si solo hay factores de capacidad."
    )


def b6_storage(c: dict) -> None:
    st.markdown("**B6. Almacenamiento — separar MW y MWh**")
    n = c["n"]
    _tag("datos", c["escenario"], c["epoca"], "BESS/bombeo si existen en el nc o en Inversiones")
    if n.storage_units.empty:
        st.info("Este caso no tiene StorageUnit. Ejemplo pedagógico 🎨: 100 MW / 400 MWh (4 h).")
        inject(
            f"""{TAG_ILUST}<p><b>100 MW</b> (potencia) · <b>400 MWh</b> (energía) · 4 h nominales.
            No se anima descarga mayor que el SOC.</p>""",
            90,
        )
        return
    su = n.storage_units[["p_nom", "max_hours"]].copy()
    su["MWh"] = su["p_nom"] * su["max_hours"]
    st.dataframe(su, **stretch())
    st.caption("Opción línea vs batería vs ambas: solo tras Inversiones/HiGHS. Una batería no sustituye toda función de un corredor.")


def b7_despacho(c: dict) -> None:
    st.markdown("**B7. Despacho horario**")
    h = st.slider(
        "Hora (índice de snapshot)",
        0,
        max(len(c["load"]) - 1, 0),
        0,
        key=_wk("b7h", c.get("key_id") or c["label"]),
    )
    load = c["load"]
    if load.empty:
        st.info("Sin carga.")
        return
    _tag("datos", c["escenario"], c["epoca"], f"snapshot {h} · MW")
    src = c["dispatch"] if c["solved"] and not c["dispatch"].empty else c["avail"]
    kind = "despacho HiGHS" if c["solved"] and not c["dispatch"].empty else "disponibilidad (aún no despacho)"
    st.caption(kind)
    if src.empty:
        st.line_chart(load.reset_index(drop=True))
        return
    plot = src.rename(columns=lambda x: NICE_NAME.get(x, x)).reset_index(drop=True)
    st.area_chart(plot)
    st.line_chart(load.reset_index(drop=True).rename("demanda"))
    row = plot.iloc[min(h, len(plot) - 1)]
    dem = float(load.reset_index(drop=True).iloc[min(h, len(load) - 1)])
    gen = float(row.sum())
    st.markdown("**Hora crítica 🔄 — variables asociadas, no «causa demostrada»**")
    st.write(pd.DataFrame({"MW": row}))
    st.write(f"Demanda {dem:.0f} MW · suma series {gen:.0f} MW · ENS traj. **{c['shed_mwh']:.1f} MWh** (no EENS)")
    st.markdown("**Balance de auditoría** (componentes presentes): generación (+descarga) ?=? demanda (+carga) + pérdidas. Import/export si el nc las tiene.")


def b8_expansion(cases: list[dict]) -> None:
    st.markdown("**B8. Expansión de generación**")
    st.warning("Capacidad seleccionada = supuestos del caso, **no** aprobación de proyecto. No se anima un GEP nuevo sin HiGHS.")
    rows = []
    for c in cases:
        if "cap_mw" not in c:
            continue
        for car, mw in c["cap_mw"].items():
            rows.append({"escenario": c["escenario"], "época": c["epoca"], "año": c["year"], "tecnología": NICE_NAME.get(car, car), "MW": mw})
    if not rows:
        st.info("Añada épocas.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, **stretch())
    st.bar_chart(df.pivot_table(index="año", columns="tecnología", values="MW", aggfunc="sum").fillna(0))
    st.caption("Línea de tiempo por año de inicio de época. Existente = sólido. Inversiones (otra pestaña) = patrón candidato.")


def b9_tx() -> None:
    st.markdown("**B9. Expansión de transmisión**")
    inject(
        f"""
        {TAG_ILUST} {TAG_CMP}
        <div class="mde-eq">
          <div class="step">Identificación en el modelo</div>
          <div class="op">↓</div>
          <div class="step">Análisis económico (Inversiones / HiGHS)</div>
          <div class="op">↓</div>
          <div class="step">Flujo AC · contingencias · estabilidad — <b>pendiente</b> (no Motor B v1)</div>
          <div class="op">↓</div>
          <div class="step">Evaluación territorial · revisión institucional</div>
        </div>
        <p>La optimización produce una <b>alternativa de estudio</b>, no reemplaza PET/N-1 ni la UPME.</p>
        """,
        360,
    )
    st.caption("Antes/después de un refuerzo: misma escala, mismo escenario, misma hora. Rojo ≠ incumplimiento real.")


def b10_ens(c: dict) -> None:
    st.markdown("**B10. Confiabilidad**")
    _tag("datos", c["escenario"], c["epoca"], "ENS de esta trayectoria — no EENS, no LOLE")
    st.write(f"ENS de la trayectoria seleccionada: **{c['shed_mwh']:,.1f} MWh** (shedding del LP, si hubo despacho).")
    if c["solved"] and not c["dispatch"].empty and "load shedding" in c["dispatch"].columns:
        st.area_chart(c["dispatch"]["load shedding"].reset_index(drop=True))
    else:
        st.caption("Sin shedding horario hasta Resolver. No hay histograma probabilístico (no hay muestreo documentado).")
    st.info("Comparar portafolios (más BESS, más red, más firme) = varias épocas/Inversiones, no un EENS.")


def b11_costos(last_outdir) -> None:
    st.markdown("**B11. Costos y emisiones de generación**")
    st.caption("Costo del LP ≠ tarifa al usuario. No sume emisiones de plantas a las atribuidas del Motor A.")
    if not last_outdir:
        st.info("Sin corrida HiGHS: no hay objective_usd. No se inventa un progreso de solver.")
        return
    root = Path(last_outdir)
    costs = root / "system_costs.csv"
    if costs.exists():
        df = pd.read_csv(costs)
        st.dataframe(df, hide_index=True, **stretch())
        if "objective_usd" in df.columns:
            st.bar_chart(df.set_index(df.get("epoch", df.index.astype(str)))["objective_usd"])
        _tag("datos", "última corrida", "—", "ud. del modelo, no COP de tarifa")
    else:
        st.info("No está system_costs.csv.")


def b12_estres(c: dict) -> None:
    st.markdown("**B12. Estrés**")
    _tag("cmp", c["escenario"], c["epoca"], "amenazas = palancas de la época, no una probabilidad")
    inject(
        f"""
        {TAG_CMP}
        <div class="mde-eq">
          <div class="step">Evento (Niño, carbón off, demanda C3…)</div>
          <div class="op">↓</div>
          <div class="step">Variables ya aplicadas en apply_levers</div>
          <div class="op">↓</div>
          <div class="step">Ejecución HiGHS (si corrió)</div>
          <div class="op">↓</div>
          <div class="step">Comparar con otra época de la cola</div>
        </div>
        <p>Cascada <i>definida en el modelo</i>: menos p_max_pu hidro → menos MW hidro disponibles → más térmica si el despacho la usa.
        Eso no es una causalidad automática animada sin resultados.</p>
        """,
        340,
    )
    st.write(
        {
            "demanda": c["ep"].get("demand_scenario"),
            "hidro": c["ep"].get("hydrology_scenario"),
            "clima": c["ep"].get("climate_scenario"),
            "carbón_off": c["ep"].get("coal_phase_out"),
        }
    )


def b13_comparar(cases: list[dict]) -> None:
    st.markdown("**B13. Comparación de escenarios**")
    st.caption("Rango entre escenarios ≠ intervalo de confianza. Frecuencia de un proyecto ≠ probabilidad.")
    rows = []
    for c in cases:
        if "n" not in c:
            continue
        rows.append(
            {
                "escenario": c["escenario"],
                "época": c["epoca"],
                "año": c["year"],
                "demanda_MWh_pond": c["demand_mwh"],
                "ENS_MWh_trayectoria": c["shed_mwh"],
                "p_nom_MW": float(c["cap_mw"].sum()) if len(c["cap_mw"]) else 0,
                "red": c.get("key"),
                "despachado": c["solved"],
            }
        )
    if not rows:
        st.info("Cola vacía.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df.round(1), hide_index=True, **stretch())
    st.bar_chart(df.set_index(df["escenario"] + " · " + df["época"])["demanda_MWh_pond"])
    if len(df) > 1:
        st.caption(
            f"Rango de demanda ponderada entre casos: {df.demanda_MWh_pond.min():,.0f} – {df.demanda_MWh_pond.max():,.0f} MWh. "
            "No es un IC estadístico."
        )


def b14_audit(last_outdir, run_log: str | None) -> None:
    st.markdown("**B14. Ejecución y auditoría**")
    st.caption("Si no hay % real del solver, se muestra etapa, no una barra inventada.")
    stages = [
        "1. Validando datos",
        "2. Construyendo red",
        "3. Construyendo problema",
        "4. Enviando al solucionador",
        "5. Resolviendo HiGHS",
        "6. Validando resultados",
        "7. Figuras",
        "8. Disponible",
    ]
    done = bool(last_outdir)
    items = "".join(
        f"<div class='step'>{s} — {'terminado' if done else 'pendiente / en cola'}</div>" for s in stages
    )
    inject(f"{TAG_DATOS}<div class='mde-eq'>{items}</div>", 420)
    st.write({"last_outdir": last_outdir, "run_log": run_log or "—", "solver": "highs (si se lanzó)"})
    st.caption("Infactibilidad: no se afirma «fue la transmisión» si varias restricciones participan. Historial = carpeta de la corrida.")


def puentes_ab() -> None:
    st.markdown("**Puente Motor A → B**")
    inject(
        f"""
        {TAG_CMP}
        <div class="mde-eq">
          <div class="step">Hogares / buses / industria (Motor A)</div>
          <div class="op">↓</div>
          <div class="step">PJ o GWh anuales + perfil lun–dom</div>
          <div class="op">↓</div>
          <div class="step">Nodo (no por población si es una cementera)</div>
          <div class="op">↓</div>
          <div class="step">Despacho y red (Motor B / HiGHS)</div>
        </div>
        <p>La electrificación no se juzga solo por el kWh nuevo: también por el combustible desplazado y la respuesta del sistema.
        Carga EV gestionada vs no gestionada solo si ambos casos se modelaron.</p>
        """,
        340,
    )


def render_suite(epochs, preview_fn, last_outdir=None, run_log=None, sections: str = "all") -> None:
    """sections: all | demand | gen | summary | config — only the Motor B tab should call this."""
    global _NS
    _NS = str(sections or "all")
    st.markdown("---")
    st.markdown("### Motor B — expansión y operación (datos de **esta** cola de escenarios × épocas)")
    st.caption("🎨 ilustrativa · 📊 caso bajo estudio · 🔄 comparativa. MW ≠ MWh. ENS ≠ EENS.")
    if not epochs:
        st.info("Añada épocas en Escenario y épocas.")
        puentes_ab()
        return
    with st.spinner("Cargando redes de las épocas (palancas, no necesariamente HiGHS)…"):
        cases = collect_cases(epochs, preview_fn)
    err = [c for c in cases if "error" in c]
    for e in err:
        sc = e.get("escenario") or (e.get("ep") or {}).get("global_scenario") or "—"
        epn = e.get("epoca") or (e.get("ep") or {}).get("name") or "—"
        st.warning(f"{sc} · {epn}: {e['error']}")
    c = _pick(cases, key="pick")
    if c is None:
        return
    mapping = {
        "all": "b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 b11 b12 b13 b14 ab",
        "config": "b14 b12 b1 ab",
        "summary": "b13 b11 b8 b10 b9",
        "demand": "b7 b1 ab",
        "gen": "b3 b4 b5 b6 b7 b8",
    }
    want = mapping.get(sections, mapping["all"]).split()
    if "b1" in want:
        b1_panorama(c)
    if "b2" in want:
        b2_red(c)
    if "b3" in want:
        b3_generacion(c)
    if "b4" in want:
        b4_hidro(c)
    if "b5" in want:
        b5_vre(c)
    if "b6" in want:
        b6_storage(c)
    if "b7" in want:
        b7_despacho(c)
    if "b8" in want:
        b8_expansion(cases)
    if "b9" in want:
        b9_tx()
    if "b10" in want:
        b10_ens(c)
    if "b11" in want:
        b11_costos(last_outdir)
    if "b12" in want:
        b12_estres(c)
    if "b13" in want:
        b13_comparar(cases)
    if "b14" in want:
        b14_audit(last_outdir, run_log)
    if "ab" in want:
        puentes_ab()
