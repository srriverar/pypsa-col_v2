"""Motor A — 13 pestañas de planeación + paquete LEAP, con animaciones etiquetadas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from . import animations as A
from .beco import reconcile
from .catalog import BECO_NOTE, EF_ELEC_T_PER_MWH, GWP_VERSION, PEN_SCENARIOS
from .engine import RunConfig, national_by_year, run
from .equivalence import compare_gold, function_suite, implied_ef_t_per_tj, load_celdas, matrix_frame
from .methods import useful_to_final
from .package import inventory
from .policies import DEFAULT_POLICIES
from .profiles import pypsa_contract, weekday_hour_weights
from .tree import as_frame


def tab_motor_a() -> None:
    st.markdown(
        """
<div class="legend-box">
<b>Motor A</b> = demanda energética y emisiones (LEAP-like). <b>Motor B</b> = la pestaña GUI / PyPSA.<br>
Cada animación lleva etiqueta <b>🎨 ilustrativa</b> (no es el modelo) o <b>📊 datos del anexo PEN</b>
(escenario histórico, no el pronóstico de 2026). PEN y NDC no se fusionan.
</div>
""",
        unsafe_allow_html=True,
    )
    reduce = st.checkbox("Reducir movimiento", value=False, key="mde_reduce")
    if reduce:
        st.markdown("<style>.flow-line,.mde-eq .step{animation:none!important}</style>", unsafe_allow_html=True)

    sc = st.selectbox("Escenario PEN (alimenta las vistas 📊)", PEN_SCENARIOS, key="mde_sc_global")
    year = st.slider("Año", 2019, 2052, 2030, key="mde_year_global")
    st.caption("▶ el año se elige aquí (equivalente a Reproducir/Pausar). Velocidad: muévalo usted. Vista estática = este mismo slider quieto.")

    tabs = st.tabs(
        [
            "0. Paquete LEAP",
            "A1. Panorama",
            "A2. Árbol",
            "A3. Residencial",
            "A4. Transporte",
            "A5. Industria",
            "A6. Terciario",
            "A7. Agro/minería",
            "A8. Eficiencia",
            "A9. Medidas",
            "A10. Emisiones",
            "A11. Territorio",
            "A12. BECO",
            "A13. → PyPSA",
        ]
    )
    with tabs[0]:
        _tab_paquete()
    with tabs[1]:
        _tab_a1(sc, year)
    with tabs[2]:
        _tab_a2()
    with tabs[3]:
        _tab_a3()
    with tabs[4]:
        _tab_a4()
    with tabs[5]:
        _tab_a5()
    with tabs[6]:
        st.markdown("**A6 Comercial y público.** 🎨 Edificio por capas (ilustración). 📊 El anexo agrega *Terciario*.")
        A.formula_viaje("A")
        celdas = load_celdas()
        sub = celdas[(celdas.escenario == sc) & (celdas.año == year) & (celdas.bloque.str.contains("Terciario", na=False))]
        st.bar_chart(sub.groupby("energetico")["valor"].sum())
        st.caption(f"📊 {sc} · {year} · Terciario PJ. Curva horaria de un hospital: perfil sintético, no una medición.")
    with tabs[7]:
        st.markdown("**A7 Agropecuario y minería.** El anexo junta agro + construcción + minería. Emisiones fugitivas: vista propia, no se infieren del kWh.")
        A.formula_viaje("A")
        celdas = load_celdas()
        sub = celdas[(celdas.escenario == sc) & (celdas.año == year) & (celdas.bloque.str.contains("Agro", na=False))]
        st.bar_chart(sub.groupby("energetico")["valor"].sum())
    with tabs[8]:
        st.markdown("**A8 Tecnologías.** Cambiar tecnología ≠ cambiar combustible. Compare el **mismo servicio**.")
        A.formula_viaje("coccion")
        cols = st.columns(3)
        for col, name, eta in zip(cols, ["Leña", "GLP", "Eléctrica"], [0.15, 0.40, 0.80]):
            with col:
                st.markdown(f"**Estufa {name}** η={eta}")
                st.write(f"100 GJ útiles → **{useful_to_final(100, eta):.0f} GJ finales**")
        st.caption("🎨 Mismo servicio de cocción. Una meta de *ventas* eficientes ≠ participación de todo el parque.")
    with tabs[9]:
        _tab_a9(sc)
    with tabs[10]:
        _tab_a10(sc)
    with tabs[11]:
        st.markdown("**A11 Territorio.** 🎨 Mapa pedagógico. 📊 El anexo PEN es **nacional**. No anime municipios si el dato es departamental.")
        st.info("Asignar demanda por población puede valer para residencial; no para una cementera ni un data center.")
        st.caption("Limitaciones de encuesta DANE: no extrapole etnia × municipio × combustible sin dominio de representatividad.")
    with tabs[12]:
        st.markdown("**A12 Calibración BECO.** Verde/ámbar/rojo son tolerancias *configurables*, no un estándar oficial.")
        rec = reconcile(run(RunConfig(scenario=sc))["consumo"], 2023)
        rec["semaforo"] = rec["delta_pct"].abs().map(lambda x: "verde" if x < 5 else ("ámbar" if x < 15 else "rojo") if pd.notna(x) else "—")
        st.dataframe(rec.round(2), hide_index=True, use_container_width=True)
        st.bar_chart(rec[rec.sector != "TOTAL"].set_index("sector")[["BECO_pj", "modelo_pj"]])
        st.caption(BECO_NOTE)
    with tabs[13]:
        _tab_a13(sc, year)


def _tab_paquete() -> None:
    st.subheader("Paquete LEAP Colombia (descarga 28 oct 2026)")
    st.markdown(
        "No es un clon ejecutable de LEAP. SHA-256 del PEN `.leap`, anexo y ZIP NDC **coinciden** con los portales. "
        "Los `.leap` van con AES: se listan, no se extraen fórmulas."
    )
    inv = inventory()
    st.dataframe(
        pd.DataFrame(inv)[["nombre", "modelo", "archivo", "integridad", "sha256"]],
        hide_index=True,
        use_container_width=True,
    )
    gold = compare_gold()
    st.markdown("**Controles del anexo (deben estar verdes)**")
    st.dataframe(gold[["hoja", "celda", "energetico", "año", "esperado_anexo", "leido_csv", "ok"]], hide_index=True, use_container_width=True)
    st.dataframe(matrix_frame(), hide_index=True, use_container_width=True)
    suite = function_suite()
    st.dataframe(suite, hide_index=True, use_container_width=True)
    st.success(f"{int(suite.ok.sum())}/{len(suite)} pruebas exactas.") if bool(suite.ok.all()) else st.error("Fallos en pruebas.")
    md = Path(__file__).resolve().parents[3] / "data" / "mde" / "INVENTARIO.md"
    if md.exists():
        with st.expander("Inventario y derechos"):
            st.markdown(md.read_text(encoding="utf-8"))


def _tab_a1(sc: str, year: int) -> None:
    st.subheader("¿Cómo consume energía Colombia en este escenario?")
    A.panorama_flujos_ilustrativo()
    st.markdown("**Sankey 📊** — anchos = PJ del anexo (consumo final, no oferta primaria).")
    A.sankey_html(year, sc)
    st.markdown("**Matriz de demanda 📊** — barras apiladas por energético. La electricidad puede ganar *participación* aunque el total baje por eficiencia.")
    piv = A.stacked_by_year(sc)
    st.bar_chart(piv.loc[[year]] if year in piv.index else piv.tail(1))
    st.line_chart(piv)
    st.caption(f"Fuente: anexo PEN · {sc} · unidad PJ/año · versión CSV extraer_anexo.py · histórico publicado, no vigente 2026.")


def _tab_a2() -> None:
    st.subheader("¿De qué partes está compuesto el modelo?")
    st.caption("🎨 El árbol se expande in situ. Ruta tipo LEAP: Residencial > Rural > Cocción > Leña.")
    st.dataframe(as_frame(), hide_index=True, use_container_width=True)
    metodo = st.radio("Viaje de un cálculo (la fórmula cambia según la rama)", ["Cocción (B)", "Stock vehículos (C)", "Intensidad (A)"], horizontal=True)
    kind = {"Cocción (B)": "coccion", "Stock vehículos (C)": "stock"}.get(metodo, "A")
    A.formula_viaje(kind)


def _tab_a3() -> None:
    st.subheader("Hogares: urbano / rural, uso combinado de leña")
    A.viviendas()
    st.markdown("**Sustitución de leña 🔄** — el hogar no abandona automáticamente la leña.")
    q_lena = st.slider("q servicio leña", 0.0, 1.0, 0.60, 0.05)
    q_glp = st.slider("q servicio GLP", 0.0, 1.0, 0.30, 0.05)
    q_el = max(0.0, 1.0 - q_lena - q_glp)
    st.caption(f"q electricidad (residual) = {q_el:.2f}. Suma de q = 1 si son categorías excluyentes de *servicio*.")
    u = 300_000.0
    e_l = useful_to_final(u * q_lena, 0.15) if q_lena else 0
    e_g = useful_to_final(u * q_glp, 0.40) if q_glp else 0
    e_e = useful_to_final(u * q_el, 0.80) if q_el else 0
    st.bar_chart(pd.Series({"Leña GJ": e_l, "GLP GJ": e_g, "Elec GJ": e_e, "Elec MWh": e_e / 3.6}))
    st.caption("🎨 Ejemplo de especificación (100 mil hogares × 3 GJ), no DANE. Dependiente del escenario.")


def _tab_a4() -> None:
    st.subheader("Movilidad, flota y combustibles")
    st.markdown("Vehículos **registrados ≠ activos ≠ ventas**. 📊 El anexo trae gasolina/diésel/electricidad de *transporte*, no el stock.")
    A.bus_electrico()
    celdas = load_celdas()
    sc = st.session_state.get("mde_sc_global", "Actualización")
    tr = celdas[(celdas.escenario == sc) & (celdas.tipo == "consumo_final") & (celdas.bloque.str.contains("Transporte", na=False))]
    piv = tr.pivot_table(index="año", columns="energetico", values="valor", aggfunc="sum").fillna(0)
    keep = [c for c in ("Gasolina", "Diesel", "Electricidad_SIN", "Gas Natural", "Kerosene-Jet") if c in piv.columns]
    st.line_chart(piv[keep])
    st.caption("📊 Anexo PEN transporte. Recarga horaria gestionada: solo si el modelo tiene restricciones reales (A13).")


def _tab_a5() -> None:
    st.subheader("Procesos industriales")
    A.cogeneracion()
    st.markdown("Energía final vs útil vs pérdidas — compare **el mismo servicio**.")
    eta = st.slider("η caldera", 0.4, 0.95, 0.80, 0.01)
    u = 15_000.0
    st.write(f"15 PJ útiles de vapor → final = **{useful_to_final(u, eta):.1f} PJ**. Una bomba de calor usaría COP, no η≤1.")
    st.caption("🎨 Sustituir carbón→gas→eléctrico es una *hipótesis* hasta validar temperatura de proceso.")


def _tab_a9(sc: str) -> None:
    st.subheader("¿Qué cambió entre el anexo y una medida?")
    st.caption("La cascada depende del **orden**. 0,90 × 0,80 = 0,72 (no 0,70).")
    picked = [p for p in DEFAULT_POLICIES if st.checkbox(p["label"], key=f"a9_{p['id']}")]
    if st.button("Aplicar sobre el anexo", type="primary"):
        base = run(RunConfig(scenario=sc, policies=[]))
        alt = run(RunConfig(scenario=sc, policies=picked))
        m = national_by_year(base["consumo"]).rename(columns={"pj": "anexo"})
        st.session_state["mde_a9"] = m.merge(national_by_year(alt["consumo"]).rename(columns={"pj": "con_medidas"}), on="year")
    if st.session_state.get("mde_a9") is not None:
        st.line_chart(st.session_state["mde_a9"].set_index("year"))
        st.dataframe(st.session_state["mde_a9"].round(1), hide_index=True, use_container_width=True)


def _tab_a10(sc: str) -> None:
    st.subheader("Dónde se emiten — tres vistas, no sumar")
    st.warning("Atribuido al kWh ≠ inventario de plantas. Biomasa: CO₂ biogénico aparte; no es ‘cero clima’.")
    celdas = load_celdas()
    emi = celdas[(celdas.escenario == sc) & (celdas.tipo == "emisiones_consumo_final")]
    cons = celdas[(celdas.escenario == sc) & (celdas.tipo == "consumo_final")]
    a, b, c = st.tabs(["Directas 📊", "kWh atribuidos 🔄", "Evitadas vs Actualización 📊"])
    with a:
        st.line_chart(emi.groupby("año")["valor"].sum().rename("MtCO2eq anexo"))
        st.caption(f"GWP {GWP_VERSION}. El anexo no separa gases.")
    with b:
        mt = cons[cons.energetico.str.startswith("Electricidad")].groupby("año")["valor"].sum()
        st.line_chart((mt * (1e15 / 3.6e9) * EF_ELEC_T_PER_MWH / 1e6).rename("Mt atribuidos"))
        st.caption(f"Factor inventario ilustrativo {EF_ELEC_T_PER_MWH} t/MWh. Vista alternativa: no sumar.")
    with c:
        ref = celdas[(celdas.escenario == "Actualización") & (celdas.tipo == "emisiones_consumo_final")]
        st.line_chart((ref.groupby("año")["valor"].sum() - emi.groupby("año")["valor"].sum()).rename("Mt vs Actualización"))
    e_g, m_g = 372.7692759648167, 26.35848190858241
    st.caption(f"Auditoría FE implícito gasolina 2030 A: {implied_ef_t_per_tj(e_g, m_g):.0f} t/TJ (CO2eq, no solo CO2).")


def _tab_a13(sc: str, year: int) -> None:
    st.subheader("De PJ anuales a curva horaria para Motor B")
    A.formula_anual_a_hora()
    st.line_chart(weekday_hour_weights())
    st.caption("📊 Pesos lun–dom ilustrativos tipo SIN. Validar Σ P Δt = E anual.")
    res = run(RunConfig(scenario=sc))
    contract = pypsa_contract(res["electricidad_mwh"], year)
    tot = float(res["electricidad_mwh"].query("year == @year")["mwh"].sum()) if year in set(res["electricidad_mwh"].year) else 0.0
    st.write(f"Electricidad anexo {sc} {year}: **{tot:,.0f} MWh**")
    st.download_button("CSV contrato PyPSA (no ejecuta HiGHS)", contract.to_csv(index=False).encode("utf-8"), file_name=f"mde_pypsa_{year}.csv")
    st.info("«Enviar a Motor B» abre esta ficha. No lanza el solver hasta que usted corre la GUI.")
