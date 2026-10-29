"""XM DemaReal often publishes a partial last 1–2 days; drop that suffix only."""

from __future__ import annotations

import pandas as pd

from pypsa_col.xm import drop_incomplete_demand_tail


def _hourly(days, hourly_kwh, start="2026-10-01"):
    idx = pd.date_range(start, periods=days * 24, freq="h")
    values = []
    for i, _ in enumerate(idx):
        day = i // 24
        values.append(hourly_kwh[day])
    return pd.DataFrame({"timestamp": idx, "value": values})


def test_drops_trailing_partial_demareal_not_mid_window():
    # 5 full days ~10 GWh/h, then 2 partial days ~2 GWh/h (the XM artefact)
    hourly = [10_000_000] * 5 + [2_000_000, 1_900_000]
    gene_h = [10_200_000] * 7
    tables = {
        "dema": _hourly(7, hourly),
        "gene_sis": _hourly(7, gene_h),
        "precio": _hourly(7, [200.0] * 7),
    }
    meta = drop_incomplete_demand_tail(tables, {"start": "2026-10-01", "end": "2026-10-07"})
    assert meta["trimmed_days"] == ["2026-10-06", "2026-10-07"]
    assert meta["end"] == "2026-10-05"
    assert pd.to_datetime(tables["dema"]["timestamp"]).max().date().isoformat() == "2026-10-05"
    assert pd.to_datetime(tables["precio"]["timestamp"]).max().date().isoformat() == "2026-10-05"
    # generation of complete days is untouched
    assert len(tables["gene_sis"]) == 5 * 24


def test_keeps_a_real_sunday_dip_when_still_sin_scale():
    # Saturday 9.5 GWh/h, Sunday 8.0 GWh/h — real weekend, not the 2 GWh artefact
    hourly = [10_000_000] * 5 + [9_500_000, 8_000_000]
    gene_h = [10_200_000] * 5 + [9_700_000, 8_200_000]
    tables = {"dema": _hourly(7, hourly), "gene_sis": _hourly(7, gene_h)}
    meta = drop_incomplete_demand_tail(tables, {})
    assert not meta.get("trimmed_days")
    assert len(tables["dema"]) == 7 * 24
