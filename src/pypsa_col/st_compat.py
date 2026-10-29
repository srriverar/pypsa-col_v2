"""Streamlit 1.66 replaced use_container_width with width='stretch'."""

from __future__ import annotations

import inspect
from functools import lru_cache


@lru_cache(maxsize=1)
def stretch() -> dict:
    try:
        import streamlit as st

        if "width" in inspect.signature(st.dataframe).parameters:
            return {"width": "stretch"}
    except Exception:
        pass
    return {"use_container_width": True}


def on_streamlit_cloud() -> bool:
    from pathlib import Path

    return Path("/mount/src").exists()
