"""Plotly charts with a clickable legend (hide/show series)."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def plot_series(
    data: pd.DataFrame | pd.Series,
    *,
    kind: str = "line",
    y_title: str = "",
    x_title: str = "",
    title: str = "",
    height: int = 420,
) -> None:
    """kind: line | area | bar. Legend click toggles a series (Plotly default)."""
    import plotly.graph_objects as go

    if data is None:
        st.info("Sin datos para graficar.")
        return
    df = data.copy()
    if isinstance(df, pd.Series):
        name = df.name or "valor"
        df = df.to_frame(name)
    if df.empty:
        st.info("Sin datos para graficar.")
        return
    df = df.apply(pd.to_numeric, errors="coerce")
    x = df.index
    if isinstance(x, pd.RangeIndex) or x.dtype == "int64":
        x_plot = list(x)
    elif isinstance(x, pd.DatetimeIndex):
        x_plot = x
    else:
        x_plot = [str(v) for v in x]

    fig = go.Figure()
    for col in df.columns:
        y = df[col]
        label = str(col)
        if kind == "area":
            fig.add_trace(go.Scatter(x=x_plot, y=y, name=label, stackgroup="one", mode="lines"))
        elif kind == "bar":
            fig.add_trace(go.Bar(x=x_plot, y=y, name=label))
        else:
            fig.add_trace(go.Scatter(x=x_plot, y=y, name=label, mode="lines"))
    fig.update_layout(
        title=title or None,
        legend=dict(
            title_text="Clic en la leyenda para quitar/poner una serie",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
        ),
        hovermode="x unified",
        yaxis_title=y_title,
        xaxis_title=x_title,
        height=height,
        margin=dict(t=70, b=40, l=50, r=20),
        barmode="group" if kind == "bar" else None,
        paper_bgcolor="#f4f1ea",
        plot_bgcolor="#fffdf8",
        font=dict(color="#1b2a41"),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Clic en un color de la leyenda para ocultar o volver a mostrar esa serie.")
