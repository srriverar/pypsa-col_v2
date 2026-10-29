"""HTTP + Streamlit-compatible stubs so Arena preview on :8501 does not 502."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
os.environ.setdefault("MPLBACKEND", "Agg")

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from starlette.routing import Route, WebSocketRoute
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketDisconnect

_MAP_DIR: Path | None = None


class FrameAllow:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrap(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((b"x-frame-options", b"ALLOWALL"))
                headers.append((b"content-security-policy", b"frame-ancestors *"))
                headers.append((b"access-control-allow-origin", b"*"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrap)


async def home(_: Request) -> HTMLResponse:
    path = ROOT / "vista_app.html"
    html = path.read_text(encoding="utf-8") if path.exists() else "<h1>PyPSA-col</h1>"
    return HTMLResponse(html)


async def health(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def host_config(_: Request) -> JSONResponse:
    return JSONResponse(
        {
            "allowedOrigins": ["*"],
            "useExternalAuthToken": False,
            "enableCustomParentMessages": True,
            "enforceDownloadInNewTab": False,
            "metricsUrl": "",
            "blockErrorDialogs": True,
            "resourceCrossOriginMode": None,
        }
    )


async def st_stream(ws: WebSocket) -> None:
    """Arena probes this; accept so the preview is not 502."""
    await ws.accept()
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        return
    except Exception:
        return


async def invest(request: Request) -> JSONResponse:
    global _MAP_DIR
    try:
        body = await request.json()
    except Exception:
        body = {}
    items = body.get("items") or []
    net = body.get("network") or "clustered-18"
    if not items:
        return JSONResponse({"error": "Elija al menos una inversión."}, status_code=400)
    try:
        from pypsa_col.gui_core import patch_linopy_pandas3
        from pypsa_col.investments import compare_investments

        patch_linopy_pandas3()
        levers = {
            "demand_scenario": "Media - C2",
            "hydrology_scenario": "Media (histórica XM)",
            "climate_scenario": "Neutral",
            "fuel_price_scenario": "Medio",
            "start_date": "2026-01-01",
            "representative_years": 1,
            "representative_months": 1,
            "representative_days": 1,
        }
        result = compare_investments(
            ROOT, [], network_key=net, levers=levers, solver="highs", custom_items=items
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=500)
    _MAP_DIR = Path(result["map_dir"]) if result.get("map_dir") else None
    k0, k1 = result["kpis_base"], result["kpis_inv"]
    table = {
        "Costo operativo": {"base": f"{k0['objective']:,.0f}", "inv": f"{k1['objective']:,.0f}"},
        "Demanda GWh": {"base": f"{k0['demand_mwh']/1e3:.1f}", "inv": f"{k1['demand_mwh']/1e3:.1f}"},
        "ENS MWh": {"base": f"{k0['shed_mwh']:.0f}", "inv": f"{k1['shed_mwh']:.0f}"},
        "FNCE %": {"base": f"{k0['fnce_pct']:.1f}", "inv": f"{k1['fnce_pct']:.1f}"},
    }
    maps = {k: Path(v).name for k, v in (result.get("maps") or {}).items() if k != "error" and v}
    return JSONResponse(
        {
            "base_status": result["base_status"],
            "inv_status": result["inv_status"],
            "table": table,
            "narrative": result.get("narrative") or "",
            "maps": maps,
            "applied": [a.get("label") for a in result.get("applied") or []],
        }
    )


async def maps(request: Request):
    name = request.path_params["name"]
    if not _MAP_DIR or not name.endswith(".png") or "/" in name or ".." in name:
        return JSONResponse({"error": "no map"}, status_code=404)
    path = _MAP_DIR / name
    if not path.exists():
        return JSONResponse({"error": "missing"}, status_code=404)
    return FileResponse(str(path), media_type="image/png")


app = Starlette(
    routes=[
        Route("/", home),
        Route("/_stcore/health", health),
        Route("/_stcore/script-health-check", health),
        Route("/_stcore/host-config", host_config),
        Route("/_stcore/metrics", health),
        Route("/health", health),
        Route("/api/invest", invest, methods=["POST"]),
        Route("/maps/{name}", maps),
        WebSocketRoute("/_stcore/stream", st_stream),
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(FrameAllow),
    ],
)
