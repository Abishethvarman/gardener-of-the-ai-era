"""A small HTTP server using only the standard library.

    GET  /                 the app
    GET  /api/regions      preset places
    GET  /api/features     which optional features are switched on
    GET  /api/crops        crop list (for the diary)
    GET  /api/plan         ?region=delhi | ?onset=06-27&withdrawal=09-25&cool=1
                           optional: &date=YYYY-MM-DD &brief=model|template &lang=hi
    GET  /api/water        same place params (+ lat/lon for custom dates)
    GET  /api/balcony      same place params + &sun=4&pots=6
    POST /api/photo        {"image": dataURL, "note": "...", place params}
    POST /api/packet       {"image": dataURL, place params}
    POST /api/ask          {"question": "...", place params}
    POST /api/diary        {"entries": [{"crop": "Spinach", "planted": "2026-10-01"}], place params}
    GET  /api/health       model reachability
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import features
from .crops import CROPS
from .engine import PlanError, make_plan
from .features import FeatureError
from .regions import list_regions
from .service import Planner, parse_day, region_from

STATIC = Path(__file__).parent / "static"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/icon.svg": ("icon.svg", "image/svg+xml"),
}
MAX_BODY = 9_000_000
FEATURE_ROUTES = {
    "/api/water": "water", "/api/balcony": "balcony", "/api/photo": "photo",
    "/api/packet": "packet", "/api/ask": "ask", "/api/diary": "diary",
}


def make_handler(planner: Planner, enabled: set[str] | None = None):
    on = features.enabled() if enabled is None else enabled

    class Handler(BaseHTTPRequestHandler):
        server_version = "Gardener/0.3"

        def log_message(self, fmt, *args):
            if os.environ.get("GARDENER_LOG"):
                super().log_message(fmt, *args)

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _handle(self, path: str, params: dict) -> None:
            feature = FEATURE_ROUTES.get(path)
            if feature and feature not in on:
                return self._json(404, {"error": "This feature is turned off."})
            try:
                today = parse_day(params.get("date"))
                if path == "/api/plan":
                    lang = params.get("lang") if "language" in on else None
                    region = region_from(params)
                    return self._json(200, planner.plan(today, region, params.get("brief", "model") != "template", lang))
                if path == "/api/water":
                    from .features.water import water_tip
                    region = region_from(params)
                    return self._json(200, water_tip(region.lat, region.lon, today))
                if path == "/api/balcony":
                    from .features.balcony import suggest
                    try:
                        sun, pots = float(params.get("sun", 6)), int(params.get("pots", 6))
                    except ValueError:
                        raise FeatureError("Sun hours and pots should be numbers.") from None
                    return self._json(200, suggest(make_plan(today, region_from(params)), sun, pots))
                if path == "/api/diary":
                    from .features.diary import harvest_plan
                    region = region_from(params) if (params.get("region") or params.get("onset")) else None
                    return self._json(200, harvest_plan(params.get("entries", []), today, region))
                if path == "/api/ask":
                    from .features.ask import ask
                    plan = make_plan(today, region_from(params))
                    return self._json(200, ask(params.get("question", ""), plan, today, planner.client))
                if path in ("/api/photo", "/api/packet"):
                    region = region_from(params)
                    if path == "/api/packet":
                        from .features.packet import read_packet
                        return self._json(200, read_packet(params.get("image"), region, today, planner.client))
                    from .features.ask import season_line
                    from .features.photo import check_plant
                    season = season_line(make_plan(today, region))
                    return self._json(200, check_plant(params.get("image"), planner.client, region.where, season, params.get("note")))
            except (PlanError, FeatureError) as e:
                return self._json(400, {"error": str(e)})
            self._json(404, {"error": "not found"})

        def do_GET(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            if url.path in STATIC_FILES:
                name, ctype = STATIC_FILES[url.path]
                try:
                    return self._send(200, (STATIC / name).read_bytes(), ctype)
                except FileNotFoundError:
                    return self._json(404, {"error": "not found"})
            if url.path == "/api/regions":
                return self._json(200, list_regions())
            if url.path == "/api/features":
                return self._json(200, {"enabled": sorted(on)})
            if url.path == "/api/crops":
                return self._json(200, [{"name": c["name"], "days_to_harvest": c["days_to_harvest"]} for c in CROPS])
            if url.path == "/api/health":
                c = planner.client
                return self._json(200, {"ok": True, "model": c.model, "model_enabled": c.enabled, "model_reachable": c.available()})
            if url.path in ("/api/photo", "/api/packet", "/api/ask", "/api/diary"):
                return self._json(405, {"error": "Use POST for this endpoint."})
            self._handle(url.path, {k: v[0] for k, v in parse_qs(url.query).items()})

        def do_POST(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            if url.path not in ("/api/photo", "/api/packet", "/api/ask", "/api/diary"):
                return self._json(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length <= 0 or length > MAX_BODY:
                return self._json(413 if length > MAX_BODY else 400, {"error": "Send a JSON body under 9 MB."})
            try:
                params = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(params, dict):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                return self._json(400, {"error": "The request body should be a JSON object."})
            self._handle(url.path, params)

    return Handler


def serve(host: str | None = None, port: int | None = None, planner: Planner | None = None) -> None:
    host = host or os.environ.get("HOST", "0.0.0.0")
    port = port or int(os.environ.get("PORT", "8000"))
    planner = planner or Planner()
    httpd = ThreadingHTTPServer((host, port), make_handler(planner))
    c = planner.client
    mode = f"{c.model} via {c.base_url}" if c.enabled else "built-in writer only"
    print(f"Gardener on http://{host}:{port}  (model: {mode}; features: {', '.join(sorted(features.enabled())) or 'none'})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")
    finally:
        httpd.server_close()
