"""HTML/CSS/JS animations for Motor A. 🎨 illustrative vs 📊 data-backed."""

from __future__ import annotations

import json

import pandas as pd
import streamlit.components.v1 as components

from .equivalence import load_celdas

FUEL_COLOR = {
    "Electricidad_SIN": "#E8C547",
    "Electricidad_AUT_COG": "#F5D76E",
    "Gas Natural": "#2E6DA4",
    "GLP": "#6B5B95",
    "Gasolina": "#C0392B",
    "Diesel": "#E67E22",
    "Carbón Mineral": "#4A4A4A",
    "Leña": "#6B4F2A",
    "Bagazo": "#7A8450",
    "Hidrogeno": "#1ABC9C",
    "Kerosene-Jet": "#D35400",
    "Fuel Oil": "#922B21",
    "Coque": "#2C3E50",
    "Avgas": "#E74C3C",
    "Petróleo": "#7B241C",
    "Residuos": "#5D6D3C",
    "Carbón de Leña": "#5C4033",
}

TAG_ILUST = '<span style="background:#fff3cd;border:1px solid #e0c48a;padding:1px 6px;border-radius:4px;font-size:0.8rem">🎨 Ilustrativa — no es un resultado del modelo</span>'
TAG_DATOS = '<span style="background:#d4edda;border:1px solid #8fbc8f;padding:1px 6px;border-radius:4px;font-size:0.8rem">📊 Datos del anexo PEN (escenario histórico)</span>'
TAG_CMP = '<span style="background:#d6eaf8;border:1px solid #7fb3d5;padding:1px 6px;border-radius:4px;font-size:0.8rem">🔄 Comparativa</span>'

_CSS = """
<style>
@keyframes mde-draw { to { stroke-dashoffset: 0; } }
@keyframes mde-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes mde-pulse { 0%,100% { opacity: .7 } 50% { opacity: 1 } }
@keyframes mde-flow { to { stroke-dashoffset: -24; } }
.mde-wrap { font-family: Georgia, serif; color: #1c2330; }
.mde-tag { margin-bottom: 8px; }
.mde-legend { display:flex; flex-wrap:wrap; gap:8px 14px; font-size:12px; margin:8px 0; }
.mde-legend i { display:inline-block; width:12px; height:12px; border-radius:2px; margin-right:4px; vertical-align:middle; }
.mde-house { display:flex; gap:16px; flex-wrap:wrap; }
.mde-card { background:#fff; border:1px solid #d9d2c5; border-radius:8px; padding:12px; flex:1; min-width:260px; }
.mde-card h4 { margin:0 0 8px 0; }
.mde-eq { display:flex; flex-direction:column; gap:6px; align-items:center; font-size:15px; }
.mde-eq .step { padding:8px 14px; border:1px solid #d9d2c5; border-radius:6px; background:#f7f4ee;
  animation: mde-fade .5s ease both; }
.mde-eq .step:nth-child(1){animation-delay:.0s} .mde-eq .step:nth-child(2){animation-delay:.15s}
.mde-eq .step:nth-child(3){animation-delay:.3s} .mde-eq .step:nth-child(4){animation-delay:.45s}
.mde-eq .step:nth-child(5){animation-delay:.6s} .mde-eq .step:nth-child(6){animation-delay:.75s}
.mde-eq .op { color:#b85716; font-weight:700; }
.reduce .mde-eq .step { animation: none; }
.bus { display:flex; align-items:center; gap:20px; }
.bus .veh { font-size:42px; }
.flow-line { stroke-dasharray: 8 6; animation: mde-flow 1s linear infinite; }
.reduce .flow-line { animation: none; }
</style>
"""


def fuel_legend_html(fuels: list[str] | None = None) -> str:
    keys = fuels or list(FUEL_COLOR)
    bits = "".join(
        f"<i style='background:{FUEL_COLOR.get(f,'#888')}'></i>{f}" for f in keys
    )
    return f"<div class='mde-legend'>{bits}</div>"


def inject(html: str, height: int = 420) -> None:
    components.html(_CSS + f"<div class='mde-wrap'>{html}</div>", height=height, scrolling=True)


def panorama_flujos_ilustrativo() -> None:
    fuels = [
        ("Electricidad_SIN", 80, 40, 280, 90),
        ("Gas Natural", 80, 80, 280, 150),
        ("Gasolina", 80, 120, 280, 210),
        ("Leña", 80, 160, 280, 270),
        ("Diesel", 80, 200, 280, 330),
    ]
    lines = []
    for f, x1, y1, x2, y2 in fuels:
        c = FUEL_COLOR[f]
        lines.append(
            f'<line class="flow-line" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{c}" stroke-width="4"/>'
            f'<text x="{x1-8}" y="{y1+4}" font-size="11" text-anchor="end" fill="{c}">{f}</text>'
        )
    html = f"""
    <div class="mde-tag">{TAG_ILUST}</div>
    <svg viewBox="0 0 520 360" width="100%" height="360">
      <rect x="270" y="60" width="200" height="50" fill="#f7f4ee" stroke="#b85716"/>
      <text x="370" y="90" text-anchor="middle">Viviendas</text>
      <rect x="270" y="125" width="200" height="50" fill="#f7f4ee" stroke="#b85716"/>
      <text x="370" y="155" text-anchor="middle">Industria</text>
      <rect x="270" y="190" width="200" height="50" fill="#f7f4ee" stroke="#b85716"/>
      <text x="370" y="220" text-anchor="middle">Transporte</text>
      <rect x="270" y="255" width="200" height="50" fill="#f7f4ee" stroke="#b85716"/>
      <text x="370" y="285" text-anchor="middle">Cocción rural</text>
      <rect x="270" y="310" width="200" height="40" fill="#f7f4ee" stroke="#b85716"/>
      <text x="370" y="335" text-anchor="middle">Maquinaria</text>
      {''.join(lines)}
    </svg>
    <p style="font-size:13px">Esquema ilustrativo. El ancho de los flujos <b>no</b> representa cantidades.</p>
    """
    inject(html, 420)


def sankey_html(year: int, scenario: str) -> None:
    df = load_celdas()
    sub = df[(df.escenario == scenario) & (df.año == year) & (df.tipo == "consumo_final")]
    if sub.empty:
        inject("<p>Sin datos para ese año/escenario.</p>", 80)
        return
    by = sub.groupby(["energetico", "bloque"])["valor"].sum().reset_index()
    total = float(by.valor.sum()) or 1.0
    fuels = by.groupby("energetico")["valor"].sum().sort_values(ascending=False)
    sectors = by.groupby("bloque")["valor"].sum().sort_values(ascending=False)
    n_f, n_s = len(fuels), len(sectors)
    h = max(280, 28 * max(n_f, n_s) + 40)
    fy = {f: 20 + i * (h - 40) / max(n_f, 1) for i, f in enumerate(fuels.index)}
    sy = {s: 20 + i * (h - 40) / max(n_s, 1) for i, s in enumerate(sectors.index)}
    paths = []
    for _, row in by.iterrows():
        w = max(1.2, 40 * float(row.valor) / total)
        c = FUEL_COLOR.get(row.energetico, "#888")
        y1, y2 = fy[row.energetico], sy[row.bloque]
        paths.append(
            f'<path d="M 180 {y1} C 280 {y1}, 280 {y2}, 380 {y2}" fill="none" stroke="{c}" '
            f'stroke-width="{w}" opacity="0.75" class="flow-line"/>'
        )
    left = "".join(
        f'<text x="170" y="{fy[f]+4}" text-anchor="end" font-size="11">{f} ({v:.0f} PJ)</text>'
        for f, v in fuels.items()
    )
    right = "".join(
        f'<text x="390" y="{sy[s]+4}" font-size="11">{s.replace("Sector ","")[:28]} ({v:.0f})</text>'
        for s, v in sectors.items()
    )
    html = f"""
    <div class="mde-tag">{TAG_DATOS} · {scenario} · {year} · consumo final {total:,.0f} PJ/año</div>
    {fuel_legend_html(list(fuels.index)[:12])}
    <svg viewBox="0 0 700 {h}" width="100%" height="{min(h,520)}">
      {''.join(paths)}{left}{right}
    </svg>
    """
    inject(html, min(h, 540) + 80)


def formula_viaje(kind: str = "coccion") -> None:
    if kind == "coccion":
        steps = [
            ("Hogares", "1.000 hogares  ·  supuesto ilustrativo"),
            ("×", "Servicio de cocción por hogar (GJ útil)"),
            ("×", "Participación tecnológica q (servicio, no hogares)"),
            ("÷", "Eficiencia η (leña 0,15 · GLP 0,40 · elec 0,80)"),
            ("=", "Consumo final del energético"),
        ]
        metodo = "Método B (energía útil). No todas las ramas usan esta fórmula."
    elif kind == "stock":
        steps = [
            ("N vehículos activos", "≠ registrados ≠ ventas"),
            ("×", "km / año"),
            ("×", "L/km o kWh/km"),
            ("÷", "η de carga si es eléctrico"),
            ("=", "Litros o kWh / año"),
        ]
        metodo = "Método C (stock). Transporte carretero."
    else:
        steps = [
            ("Actividad A", "toneladas, m², COP constantes…"),
            ("×", "Intensidad final I"),
            ("=", "Energía final E"),
        ]
        metodo = "Método A. Minería, aéreo, industria sin detalle."
    body = []
    for i, (a, b) in enumerate(steps):
        cls = "op" if a in {"×", "÷", "="} else ""
        body.append(f'<div class="step {cls}"><b>{a}</b><br><span style="font-size:12px">{b}</span></div>')
    html = f"""
    <div class="mde-tag">{TAG_ILUST} · {TAG_CMP}</div>
    <p>{metodo}</p>
    <div class="mde-eq">{''.join(body)}</div>
    """
    inject(html, 420)


def viviendas() -> None:
    html = f"""
    <div class="mde-tag">{TAG_ILUST}</div>
    <div class="mde-house">
      <div class="mde-card">
        <h4>Vivienda urbana</h4>
        <svg viewBox="0 0 200 140" width="100%" height="140">
          <rect x="40" y="50" width="120" height="80" fill="#f7f4ee" stroke="#b85716"/>
          <polygon points="40,50 100,15 160,50" fill="#e8c547" stroke="#b85716"/>
          <rect x="90" y="90" width="20" height="40" fill="#2e6da4"/>
          <circle cx="70" cy="80" r="8" fill="#e67e22"><title>Cocina</title></circle>
          <rect x="130" y="70" width="18" height="28" fill="#6b5b95"><title>Nevera</title></rect>
        </svg>
        <p style="font-size:13px">Cocina (GN/GLP/elec) · nevera · iluminación · TV · A/A o ventilador · calentador.</p>
      </div>
      <div class="mde-card">
        <h4>Vivienda rural</h4>
        <svg viewBox="0 0 200 140" width="100%" height="140">
          <rect x="50" y="60" width="100" height="70" fill="#f7f4ee" stroke="#6b4f2a"/>
          <polygon points="50,60 100,25 150,60" fill="#7a8450" stroke="#6b4f2a"/>
          <circle cx="75" cy="95" r="10" fill="#6b4f2a"><title>Leña</title></circle>
          <circle cx="110" cy="95" r="8" fill="#6b5b95"><title>GLP</title></circle>
        </svg>
        <p style="font-size:13px">Cocina de leña y/o GLP · iluminación · refrigeración · bomba si aplica · red o ZNI.</p>
      </div>
    </div>
    <p style="font-size:13px">Pedagógico: no es el comportamiento exacto de todos los hogares. El uso combinado de leña+GLP es la regla, no la excepción.</p>
    """
    inject(html, 280)


def bus_electrico() -> None:
    html = f"""
    <div class="mde-tag">{TAG_ILUST} · {TAG_CMP}</div>
    <div class="bus">
      <div>
        <div class="veh">🚌</div>
        <p><b>Diésel</b><br>0,40 L/km · emisiones de escape</p>
      </div>
      <div style="font-size:28px;color:#b85716">→</div>
      <div>
        <div class="veh">🚌</div>
        <p><b>Eléctrico</b><br>1,20 kWh/km en batería · ÷ 0,90 carga = red</p>
      </div>
    </div>
    <p>100 buses × 60.000 km → <b>−2,4 millones L diésel/año</b> y <b>+8 GWh</b> en el punto de carga.</p>
    <p style="font-size:13px"><b>Cero emisiones de escape</b> en esta representación; las de generación eléctrica se reportan <b>aparte</b> y no se suman al inventario territorial.</p>
    """
    inject(html, 240)


def cogeneracion() -> None:
    html = f"""
    <div class="mde-tag">{TAG_ILUST}</div>
    <svg viewBox="0 0 520 160" width="100%" height="160">
      <rect x="20" y="60" width="120" height="40" fill="#4a4a4a" />
      <text x="80" y="85" fill="white" text-anchor="middle" font-size="12">Combustible</text>
      <line class="flow-line" x1="140" y1="80" x2="220" y2="80" stroke="#4a4a4a" stroke-width="4"/>
      <rect x="220" y="50" width="110" height="60" fill="#f7f4ee" stroke="#b85716"/>
      <text x="275" y="85" text-anchor="middle" font-size="12">Cogenerador</text>
      <line class="flow-line" x1="330" y1="60" x2="410" y2="30" stroke="#e8c547" stroke-width="4"/>
      <line class="flow-line" x1="330" y1="100" x2="410" y2="130" stroke="#c0392b" stroke-width="4"/>
      <text x="500" y="34" text-anchor="end">Electricidad</text>
      <text x="500" y="134" text-anchor="end">Calor útil</text>
    </svg>
    <p>El combustible es <b>entrada de transformación</b>. No sume combustible + kWh + calor como tres consumos finales.</p>
    """
    inject(html, 220)


def formula_anual_a_hora() -> None:
    html = f"""
    <div class="mde-tag">{TAG_ILUST} · puente A → B</div>
    <div class="mde-eq">
      <div class="step">Demanda anual (PJ o GWh) del Motor A</div>
      <div class="op">↓</div>
      <div class="step">Pesos territoriales w (no usar población para una cementera)</div>
      <div class="op">↓</div>
      <div class="step">Perfil lun–dom × 24 h  ·  Σ w_h = 1</div>
      <div class="op">↓</div>
      <div class="step">Asignación a bus PyPSA</div>
      <div class="op">↓</div>
      <div class="step">Serie horaria  ·  validar Σ P Δt = E_año</div>
    </div>
    """
    inject(html, 380)


def stacked_by_year(scenario: str) -> pd.DataFrame:
    df = load_celdas()
    sub = df[(df.escenario == scenario) & (df.tipo == "consumo_final")]
    piv = sub.pivot_table(index="año", columns="energetico", values="valor", aggfunc="sum").fillna(0.0)
    # keep major fuels for a readable chart
    top = piv.sum().sort_values(ascending=False).head(8).index
    return piv[top]
