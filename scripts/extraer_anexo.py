#!/usr/bin/env python3
"""Extract numeric cells from UPME PEN 2022–2052 anexo (consumo + emisiones).

Requires: Python 3, openpyxl.
Does not recalculate Excel formulas (data_only=True).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from openpyxl.utils import get_column_letter

SCENARIO = {
    "A": "Actualización",
    "M": "Modernización",
    "I": "Inflexión",
    "D": "Disrupción",
    "LS": "Transición límite superior",
    "LI": "Transición límite inferior",
}


def _kind(sheet: str) -> tuple[str, str]:
    if sheet.startswith("Emisiones Consumo Final"):
        code = sheet.replace("Emisiones Consumo Final", "").strip()
        return "emisiones_consumo_final", code
    if sheet.startswith("Consumo Final"):
        code = sheet.replace("Consumo Final", "").strip()
        return "consumo_final", code
    return "otro", ""


def extraer(xlsx: Path) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(xlsx, data_only=True)
    rows: list[dict] = []
    for name in wb.sheetnames:
        kind, code = _kind(name)
        if kind == "otro":
            continue
        ws = wb[name]
        scenario = SCENARIO.get(code, code)
        # block name from row 10, last non-empty to the left of each fuel col
        block_at: dict[int, str] = {}
        last = None
        for c in range(1, (ws.max_column or 1) + 1):
            v = ws.cell(10, c).value
            if v:
                last = str(v).strip()
            if last:
                block_at[c] = last
        year_cols = [c for c in range(1, (ws.max_column or 1) + 1) if str(ws.cell(11, c).value or "").strip().lower() in {"año", "ano", "year"}]
        for r in range(12, (ws.max_row or 12) + 1):
            year_by_block: dict[str, int] = {}
            for yc in year_cols:
                yv = ws.cell(r, yc).value
                try:
                    yi = int(yv)
                except (TypeError, ValueError):
                    continue
                year_by_block[block_at.get(yc, "")] = yi
            for c in range(1, (ws.max_column or 1) + 1):
                header = ws.cell(11, c).value
                if header is None:
                    continue
                h = str(header).strip()
                if h.lower() in {"año", "ano", "year"}:
                    continue
                val = ws.cell(r, c).value
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    continue
                block = block_at.get(c, "")
                year = year_by_block.get(block)
                if year is None:
                    # nearest year col to the left
                    left = [yc for yc in year_cols if yc < c]
                    if left:
                        try:
                            year = int(ws.cell(r, left[-1]).value)
                        except (TypeError, ValueError):
                            year = None
                unit = "PJ-año" if "PJ" in block else ("Mt CO2eq-año" if "CO2" in block or "Mt" in block else "")
                rows.append(
                    {
                        "hoja": name,
                        "celda": f"{get_column_letter(c)}{r}",
                        "escenario_codigo": code,
                        "escenario": scenario,
                        "tipo": kind,
                        "bloque": block,
                        "energetico": h,
                        "año": year,
                        "valor": float(val),
                        "unidad": unit,
                    }
                )
    wb.close()
    return rows


def main() -> None:
    import pandas as pd

    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--xlsx",
        default=str(root / "data/mde/leap/Anexo_Resultados_PEN_2022_2052.xlsx"),
    )
    ap.add_argument(
        "--out",
        default=str(root / "data/mde/resultados_PEN_2022_2052.csv"),
    )
    args = ap.parse_args()
    rows = extraer(Path(args.xlsx))
    df = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"{len(df)} celdas → {args.out}")
    # gold checks
    g = df[(df.hoja == "Consumo Final A") & (df.celda == "I23")]
    print("gold I23 Consumo Final A", g[["energetico", "año", "valor"]].to_dict("records"))
    g = df[(df.hoja == "Consumo Final A") & (df.celda == "J23")]
    print("gold J23 Consumo Final A", g[["energetico", "año", "valor"]].to_dict("records"))


if __name__ == "__main__":
    main()
