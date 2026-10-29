#!/usr/bin/env python3
"""Build El Modelo STN + 18-subarea networks into data/streamlit/networks/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pypsa_col.stn_tesis import export_three_models  # noqa: E402


def main() -> None:
    summary = export_three_models(ROOT)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
