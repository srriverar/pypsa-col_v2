"""Colombia atlas for a UPME-style readout: demand, generation, LMP, flows.

Grid2Poster (OSM) is used as a geographic backdrop when the PNG exists.
Markers and corridors are the *model* (18 subareas / STN / 7 hubs), not PARATEC.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import pypsa

EXTENT = (-80.2, -66.4, -5.1, 13.3)  # lon0, lon1, lat0, lat1


def _poster_png(root: Path) -> Path | None:
    for rel in (
        "data/streamlit/figures/grid2poster_colombia.png",
        "data/streamlit/figures/grid2poster.png",
        "results/demo/grid2poster.png",
    ):
        p = Path(root) / rel
        if p.exists():
            return p
    return None


def _backdrop(ax, root: Path) -> None:
    png = _poster_png(root)
    ax.set_xlim(EXTENT[0], EXTENT[1])
    ax.set_ylim(EXTENT[2], EXTENT[3])
    ax.set_aspect("equal")
    ax.set_facecolor("#d7e6f0")
    if png is not None:
        img = plt.imread(png)
        ax.imshow(
            img,
            extent=[EXTENT[0], EXTENT[1], EXTENT[2], EXTENT[3]],
            aspect="equal",
            alpha=0.55,
            zorder=0,
            interpolation="bilinear",
        )
    else:
        ax.set_facecolor("#eef3ea")
    ax.set_xlabel("longitud")
    ax.set_ylabel("latitud")


def _edges(n: pypsa.Network):
    if len(n.lines):
        return n.lines, "line"
    if len(n.links):
        return n.links, "link"
    return pd.DataFrame(), "none"


def _demand_mw(n: pypsa.Network) -> pd.Series:
    if hasattr(n, "loads_t") and not n.loads_t.p_set.empty:
        s = n.loads_t.p_set.mean()
        out = pd.Series(0.0, index=n.buses.index)
        for lid, row in n.loads.iterrows():
            if lid in s.index:
                out[row.bus] = out.get(row.bus, 0.0) + float(s[lid])
        return out
    return pd.Series(0.0, index=n.buses.index)


def _gen_mw(n: pypsa.Network) -> pd.Series:
    out = pd.Series(0.0, index=n.buses.index)
    gens = n.generators
    if gens.empty:
        return out
    if hasattr(n, "generators_t") and not n.generators_t.p.empty:
        mean = n.generators_t.p.mean()
        for g, row in gens.iterrows():
            if row.carrier == "load shedding":
                continue
            out[row.bus] = out.get(row.bus, 0.0) + float(mean.get(g, 0.0))
    else:
        for g, row in gens.iterrows():
            if row.carrier == "load shedding":
                continue
            out[row.bus] = out.get(row.bus, 0.0) + float(row.p_nom)
    return out


def _lmp(n: pypsa.Network) -> pd.Series:
    if hasattr(n, "buses_t") and not n.buses_t.marginal_price.empty:
        return n.buses_t.marginal_price.mean().reindex(n.buses.index)
    return pd.Series(np.nan, index=n.buses.index)


def _flow_loading(n: pypsa.Network) -> pd.Series:
    frame, kind = _edges(n)
    if frame.empty:
        return pd.Series(dtype=float)
    load = pd.Series(0.0, index=frame.index)
    if kind == "line" and hasattr(n, "lines_t") and not n.lines_t.p0.empty:
        p = n.lines_t.p0.abs().mean()
        cap = frame["s_nom"].replace(0, np.nan)
        load = (p.reindex(frame.index) / cap).fillna(0.0)
    elif kind == "link" and hasattr(n, "links_t") and not n.links_t.p0.empty:
        p = n.links_t.p0.abs().mean()
        cap = frame["p_nom"].replace(0, np.nan)
        load = (p.reindex(frame.index) / cap).fillna(0.0)
    return load.clip(0, 1.5)


def _size(series: pd.Series, lo: float, hi: float) -> np.ndarray:
    v = series.reindex(series.index).fillna(0).to_numpy(dtype=float)
    m = float(np.nanmax(v)) if len(v) else 0.0
    if m <= 0:
        return np.full(len(v), lo)
    return lo + (hi - lo) * (v / m)


def _draw_corridors(ax, n: pypsa.Network, loading: pd.Series | None = None) -> None:
    frame, _ = _edges(n)
    if frame.empty:
        return
    for name, row in frame.iterrows():
        x = [n.buses.x[row.bus0], n.buses.x[row.bus1]]
        y = [n.buses.y[row.bus0], n.buses.y[row.bus1]]
        if loading is not None and name in loading.index:
            u = float(loading[name])
            if u < 0.5:
                c, lw = "#2ECC71", 1.2
            elif u < 0.9:
                c, lw = "#F39C12", 2.0
            else:
                c, lw = "#E74C3C", 2.8
        else:
            c, lw = "#5b7c99", 1.0
        ax.plot(x, y, color=c, lw=lw, zorder=2, solid_capstyle="round", alpha=0.9)


def _annotate(ax, n: pypsa.Network, n_max: int = 18) -> None:
    if len(n.buses) > n_max:
        return
    for name, row in n.buses.iterrows():
        ax.text(
            row.x,
            row.y,
            f" {name}",
            fontsize=6.5,
            color="#1b2a41",
            zorder=6,
            clip_on=True,
        )


def _panel(ax, n, root, title, *, mode: str) -> None:
    _backdrop(ax, root)
    demand = _demand_mw(n)
    gen = _gen_mw(n)
    prices = _lmp(n)
    loading = _flow_loading(n)
    if mode == "flujos":
        _draw_corridors(ax, n, loading)
    else:
        _draw_corridors(ax, n, None)
    if mode == "demanda":
        ax.scatter(
            n.buses.x, n.buses.y, s=_size(demand, 40, 1600),
            c="#f4a261", edgecolors="#b85716", linewidths=1.1, alpha=0.85, zorder=4,
        )
    elif mode == "generacion":
        ax.scatter(
            n.buses.x, n.buses.y, s=_size(gen, 40, 1400),
            c="#2a9d8f", edgecolors="#155e56", linewidths=1.0, alpha=0.9, zorder=4,
        )
    elif mode == "lmp":
        ax.scatter(
            n.buses.x, n.buses.y,
            s=_size(demand, 50, 900),
            facecolors="none", edgecolors="#b85716", linewidths=1.3, zorder=3,
        )
        sc = ax.scatter(
            n.buses.x, n.buses.y,
            c=prices.fillna(prices.median() if prices.notna().any() else 0),
            cmap="plasma", s=_size(gen, 60, 800),
            edgecolors="white", linewidths=0.4, zorder=4,
        )
        plt.colorbar(sc, ax=ax, shrink=0.55, label="LMP medio (ud. del modelo)")
    else:
        _draw_corridors(ax, n, loading)
        ax.scatter(
            n.buses.x, n.buses.y, s=_size(demand, 30, 900),
            facecolors="none", edgecolors="#b85716", linewidths=1.2, zorder=3,
        )
        ax.scatter(
            n.buses.x, n.buses.y, s=_size(gen, 20, 700),
            c="#2a9d8f", edgecolors="white", linewidths=0.4, alpha=0.85, zorder=4,
        )
    _annotate(ax, n)
    ax.set_title(title, fontsize=10)


def write_decision_atlas(n: pypsa.Network, root: Path, dest: Path, heading: str = "") -> dict[str, Path]:
    """Four thematic maps + a 2×2 board for the scenario/epoch folder."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    specs = [
        ("atlas_demanda.png", "demanda", f"Demanda · {heading}"),
        ("atlas_generacion.png", "generacion", f"Generación despachada · {heading}"),
        ("atlas_lmp.png", "lmp", f"Precios nodales (LMP) · {heading}"),
        ("atlas_flujos.png", "flujos", f"Carga de corredores · {heading}"),
    ]
    for fname, mode, title in specs:
        fig, ax = plt.subplots(figsize=(10.2, 12.8))
        _panel(ax, n, root, title, mode=mode)
        path = dest / fname
        fig.tight_layout()
        fig.savefig(path, dpi=155, facecolor="#f4f1ea")
        plt.close(fig)
        out[fname] = path
    fig, axes = plt.subplots(2, 2, figsize=(14.5, 17.5))
    modes = [
        (axes[0, 0], "demanda", "Demanda"),
        (axes[0, 1], "generacion", "Generación"),
        (axes[1, 0], "lmp", "LMP"),
        (axes[1, 1], "flujos", "Flujos / congestión"),
    ]
    for ax, mode, title in modes:
        _panel(ax, n, root, title, mode=mode)
    fig.suptitle(heading or "Atlas operativo Colombia", fontsize=13, y=0.995)
    fig.legend(
        handles=[
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#f4a261",
                   markeredgecolor="#b85716", markersize=9, label="Demanda"),
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#2a9d8f",
                   markeredgecolor="#155e56", markersize=9, label="Generación"),
            Line2D([0], [0], color="#E74C3C", lw=2, label="Corredor ≥90%"),
            Line2D([0], [0], color="#F39C12", lw=2, label="50–90%"),
            Line2D([0], [0], color="#2ECC71", lw=2, label="<50%"),
        ],
        loc="lower center",
        ncol=5,
        fontsize=8,
        frameon=False,
        bbox_to_anchor=(0.5, -0.01),
    )
    board = dest / "atlas_4panel.png"
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(board, dpi=150, facecolor="#f4f1ea")
    plt.close(fig)
    out["atlas_4panel.png"] = board
    return out


def _asset_style(item: dict) -> tuple[str, str, str]:
    """marker, color, legend label for an applied investment."""
    kind = str(item.get("kind") or "")
    car = str(item.get("carrier") or "")
    lab = str(item.get("label") or "")
    blob = f"{kind} {car} {lab}".casefold()
    if "eolic" in blob or "wind" in blob or car == "Wind Onshore":
        return "*", "#0e7c66", "Eólica nueva"
    if "solar" in blob or car == "Solar":
        return "^", "#c9a227", "Solar nueva"
    if "bess" in blob or kind == "storage" or "almacen" in blob:
        return "s", "#6c3483", "BESS nuevo"
    if "gas" in blob:
        return "D", "#1f4e79", "Gas nuevo"
    if "carbón" in blob or "carbon" in blob or kind == "coal_out" or kind == "coal_zone":
        return "x", "#1b1b1b", "Cierre carbón"
    if kind == "tx" or "refuerzo" in blob or "enlace" in blob:
        return "P", "#c0392b", "Refuerzo de red"
    return "o", "#b85716", "Inversión"


def write_investment_maps(
    base,
    inv,
    root: Path,
    dest: Path,
    applied: list[dict],
    heading: str = "",
) -> dict[str, Path]:
    """Before/after Colombia maps that show *this* portfolio, not a stock atlas.

    Call only after the user chose investments and HiGHS ran.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    heading = heading or "Portafolio de inversión"

    new_pts: list[tuple[float, float, str, str, str]] = []
    new_edges: list[tuple[float, float, float, float, str]] = []
    for a in applied or []:
        marker, color, leg = _asset_style(a)
        bus = a.get("bus")
        if bus is not None and str(bus) in inv.buses.index:
            row = inv.buses.loc[str(bus)]
            new_pts.append((float(row.x), float(row.y), marker, color, str(a.get("label") or bus)))
        link = a.get("link")
        if link is not None and not inv.links.empty and str(link) in inv.links.index:
            lr = inv.links.loc[str(link)]
            b0, b1 = str(lr.bus0), str(lr.bus1)
            if b0 in inv.buses.index and b1 in inv.buses.index:
                new_edges.append(
                    (
                        float(inv.buses.x[b0]),
                        float(inv.buses.y[b0]),
                        float(inv.buses.x[b1]),
                        float(inv.buses.y[b1]),
                        str(a.get("label") or "refuerzo"),
                    )
                )
        b0, b1 = a.get("bus0"), a.get("bus1")
        if b0 and b1:
            bb0 = str(b0) if str(b0) in inv.buses.index else None
            bb1 = str(b1) if str(b1) in inv.buses.index else None
            # custom tx may only store zone names
            if bb0 is None:
                hits = [i for i in inv.buses.index if str(b0).casefold()[:4] in str(i).casefold()]
                bb0 = str(hits[0]) if hits else None
            if bb1 is None:
                hits = [i for i in inv.buses.index if str(b1).casefold()[:4] in str(i).casefold()]
                bb1 = str(hits[0]) if hits else None
            if bb0 and bb1:
                new_edges.append(
                    (
                        float(inv.buses.x[bb0]),
                        float(inv.buses.y[bb0]),
                        float(inv.buses.x[bb1]),
                        float(inv.buses.y[bb1]),
                        str(a.get("label") or "refuerzo"),
                    )
                )

    def _one(ax, n, title: str, *, overlay: bool) -> None:
        _panel(ax, n, root, title, mode="generacion")
        if overlay:
            for x0, y0, x1, y1, _lab in new_edges:
                ax.plot([x0, x1], [y0, y1], color="#c0392b", lw=3.4, zorder=7, solid_capstyle="round")
                ax.plot([x0, x1], [y0, y1], color="#f5b7b1", lw=1.2, zorder=8, linestyle="--")
            for x, y, marker, color, lab in new_pts:
                ax.scatter(
                    [x], [y], s=280, marker=marker, c=color,
                    edgecolors="white", linewidths=1.1, zorder=9,
                )
                ax.text(x, y, f"  {lab[:28]}", fontsize=7, color="#1b2a41", zorder=10, fontweight="bold")

    fig, ax = plt.subplots(figsize=(10.2, 12.8))
    _one(ax, base, f"BASE (sin el portafolio) · {heading}", overlay=False)
    p = dest / "map_base_generacion.png"
    fig.tight_layout()
    fig.savefig(p, dpi=150, facecolor="#f4f1ea")
    plt.close(fig)
    out["map_base_generacion.png"] = p

    fig, ax = plt.subplots(figsize=(10.2, 12.8))
    _one(ax, inv, f"CON INVERSIONES · {heading}", overlay=True)
    p = dest / "map_inv_generacion.png"
    fig.tight_layout()
    fig.savefig(p, dpi=150, facecolor="#f4f1ea")
    plt.close(fig)
    out["map_inv_generacion.png"] = p

    fig, axes = plt.subplots(1, 2, figsize=(16.5, 11.5))
    _one(axes[0], base, "Antes (red + despacho base)", overlay=False)
    _one(axes[1], inv, "Después (MW nuevos y refuerzos)", overlay=True)
    fig.suptitle(f"Colombia · efecto espacial del portafolio · {heading}", fontsize=13)
    fig.legend(
        handles=[
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#2a9d8f",
                   markeredgecolor="#155e56", markersize=9, label="Generación despachada"),
            Line2D([0], [0], marker="*", color="none", markerfacecolor="#0e7c66",
                   markersize=12, label="Eólica / solar / BESS / gas añadido"),
            Line2D([0], [0], color="#c0392b", lw=3, label="Corredor reforzado o nuevo"),
        ],
        loc="lower center", ncol=3, fontsize=8, frameon=False, bbox_to_anchor=(0.5, -0.02),
    )
    p = dest / "map_before_after.png"
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(p, dpi=145, facecolor="#f4f1ea")
    plt.close(fig)
    out["map_before_after.png"] = p

    fig, ax = plt.subplots(figsize=(10.2, 12.8))
    _panel(ax, inv, root, f"Flujos / congestión CON inversiones · {heading}", mode="flujos")
    for x0, y0, x1, y1, _lab in new_edges:
        ax.plot([x0, x1], [y0, y1], color="#c0392b", lw=3.2, zorder=7)
    p = dest / "map_inv_flujos.png"
    fig.tight_layout()
    fig.savefig(p, dpi=150, facecolor="#f4f1ea")
    plt.close(fig)
    out["map_inv_flujos.png"] = p

    # Delta of dispatched (or p_nom) generation at each bus
    g0, g1 = _gen_mw(base), _gen_mw(inv)
    delta = (g1.reindex(inv.buses.index).fillna(0) - g0.reindex(inv.buses.index).fillna(0))
    fig, ax = plt.subplots(figsize=(10.2, 12.8))
    _backdrop(ax, root)
    _draw_corridors(ax, inv, _flow_loading(inv))
    pos, neg = delta.clip(lower=0), (-delta.clip(upper=0))
    ax.scatter(
        inv.buses.x, inv.buses.y, s=_size(pos, 20, 1600),
        c="#1abc9c", edgecolors="#0e7c66", linewidths=1.0, zorder=5, alpha=0.9,
    )
    ax.scatter(
        inv.buses.x, inv.buses.y, s=_size(neg, 20, 1200),
        c="#e74c3c", edgecolors="#7b241c", linewidths=1.0, zorder=6, alpha=0.85,
    )
    _annotate(ax, inv)
    ax.set_title(f"Δ generación en el nodo (verde +, rojo −) · {heading}", fontsize=10)
    p = dest / "map_delta_generacion.png"
    fig.tight_layout()
    fig.savefig(p, dpi=150, facecolor="#f4f1ea")
    plt.close(fig)
    out["map_delta_generacion.png"] = p
    return out
