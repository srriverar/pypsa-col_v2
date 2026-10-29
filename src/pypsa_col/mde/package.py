"""LEAP Colombia reference package (downloaded 28 Oct 2026). Hashes and paths."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

EXPECTED_SHA256 = {
    "PEN_2022_2052.leap": "86620f414fdc492ee0bc3e0d8ef080601f2ddceb994731f21cb714e584c0ac9d",
    "escbase2022v26_20_06_2023.leap": "86620f414fdc492ee0bc3e0d8ef080601f2ddceb994731f21cb714e584c0ac9d",
    "Anexo_Resultados_PEN_2022_2052.xlsx": "f454451ca02b7fa9d232d617103b81591d86681e83223509baf5625c28f1dc7c",
    "ndc_col_2020.zip": "d14664c50af681af0577abab60f31a58ad3171f04582b70dc3bc95c84b5dd05f",
}


def data_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "mde"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@lru_cache(maxsize=1)
def inventory() -> list[dict]:
    root = data_root()
    items = [
        {
            "id": "pen_2022_leap",
            "nombre": "Modelo LEAP PEN 2022–2052 (UPME)",
            "archivo": "leap/escbase2022v26_20_06_2023.leap",
            "alias": "leap/PEN_2022_2052.leap",
            "origen": "https://docs.upme.gov.co/DemandayEficiencia/Documents/PEN_2022_2052/escbase2022v26_20_06_2023.leap",
            "portal": "https://www.upme.gov.co/simec/planeacion-energetica/plan-energetico-nacional-1/",
            "nota": "ZIP/NexusDB con entradas AES. Listable, no extraíble. Abrir en LEAP autorizado.",
            "modelo": "PEN",
        },
        {
            "id": "pen_2020_leap",
            "nombre": "Modelo LEAP PEN 2020–2050 (UPME)",
            "archivo": "leap/escbase2020v25_13_11_2020.leap",
            "origen": "https://docs.upme.gov.co/DemandayEficiencia/Documents/PEN_2020_2050/escbase2020v25_13_11_2020.leap",
            "nota": "Antecesor. NexusDB; sysinfo: base 2019, 5 escenarios, 16 time-slices.",
            "modelo": "PEN",
        },
        {
            "id": "anexo_xlsx",
            "nombre": "Anexo resultados PEN 2022–2052",
            "archivo": "leap/Anexo_Resultados_PEN_2022_2052.xlsx",
            "origen": "https://docs.upme.gov.co/DemandayEficiencia/Documents/PEN_2022_2052/Anexo_Resultados_PEN_2022_2052.xlsx",
            "nota": "Resultados publicados (no parámetros internos del .leap).",
            "modelo": "PEN",
        },
        {
            "id": "anexo_csv",
            "nombre": "Extracción CSV para Motor A",
            "archivo": "resultados_PEN_2022_2052.csv",
            "origen": "scripts/extraer_anexo.py",
            "nota": "Celdas de energético con hoja, celda Excel, escenario, año, unidad.",
            "modelo": "PEN",
        },
        {
            "id": "ndc_zip",
            "nombre": "Modelo LEAP-Colombia NDC 2020 (MinAmbiente)",
            "archivo": "ndc/ndc_col_2020.zip",
            "origen": "https://www.minambiente.gov.co/wp-content/uploads/2022/09/ndc_col_2020.zip",
            "portal": "https://www.minambiente.gov.co/documento-entidad/modelo-leap-ndc-2020/",
            "nota": "ZIP con ndc_col_2020.leap (~72 MB, AES). No se descomprime para no duplicar. No es el PEN.",
            "modelo": "NDC",
        },
        {
            "id": "ndc_manual",
            "nombre": "Manual LEAP-Colombia NDC",
            "archivo": "docs/Manual_LEAP_Colombia_NDC.pdf",
            "origen": "https://www.minambiente.gov.co/wp-content/uploads/2022/09/PMR_LEAPColombia-Manual_20201209.pdf",
            "modelo": "NDC",
        },
        {
            "id": "ndc_ref",
            "nombre": "Escenarios de referencia NDC",
            "archivo": "docs/Escenarios_referencia_NDC.pdf",
            "origen": "https://www.minambiente.gov.co/wp-content/uploads/2021/10/cambio-climatico-Informe-sobre-el-desarrollo-y-los-supuestos-para-la-realizacion-de-escenarios-de-referencia-ndc.pdf",
            "modelo": "NDC",
        },
        {
            "id": "ndc_mit",
            "nombre": "Escenarios de mitigación NDC",
            "archivo": "docs/Escenarios_mitigacion_NDC.pdf",
            "origen": "https://www.minambiente.gov.co/wp-content/uploads/2021/10/cambio-climatico-Informe-sobre-el-desarrollo-supuestos-del-escenario-de-mitigacion-ndc.pdf",
            "modelo": "NDC",
        },
    ]
    out = []
    for it in items:
        p = root / it["archivo"]
        rec = {**it, "existe": p.exists(), "bytes": p.stat().st_size if p.exists() else 0}
        rec["sha256"] = sha256(p) if p.exists() and p.stat().st_size < 80_000_000 else (EXPECTED_SHA256.get(p.name) if p.exists() else "")
        if p.exists() and p.stat().st_size >= 80_000_000:
            rec["sha256"] = sha256(p)
        exp = EXPECTED_SHA256.get(Path(it["archivo"]).name)
        rec["integridad"] = "coincide" if exp and rec["sha256"] == exp else ("registrado" if rec["sha256"] else "ausente")
        if Path(it["archivo"]).name == "escbase2022v26_20_06_2023.leap" and rec["sha256"] == EXPECTED_SHA256["escbase2022v26_20_06_2023.leap"]:
            rec["integridad"] = "coincide"
        out.append(rec)
    return out
