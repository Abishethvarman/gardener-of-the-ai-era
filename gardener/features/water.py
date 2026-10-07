"""Water today? A tip from the free Open-Meteo forecast (no API key).

This is the one feature that needs internet. The decision is plain rules, not
a model, so it can be tested and trusted:

    rain today >= 5 mm       skip watering
    rain tomorrow >= 8 mm    you can skip watering
    max temperature >= 35 C  water deeply in the evening
    otherwise                check the soil with a finger first
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_cache: dict[tuple, tuple[float, dict]] = {}
CACHE_SECONDS = 3600


class WaterError(RuntimeError):
    pass


def fetch_forecast(lat: float, lon: float, timeout: float = 8.0) -> dict:
    query = urllib.parse.urlencode({
        "latitude": f"{lat:.2f}", "longitude": f"{lon:.2f}",
        "daily": "precipitation_sum,temperature_2m_max", "timezone": "auto", "forecast_days": 3,
    })
    try:
        with urllib.request.urlopen(f"{FORECAST_URL}?{query}", timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        raise WaterError("couldn't reach the forecast service") from e


def decide(forecast: dict, today: date) -> dict:
    daily = forecast.get("daily") or {}
    days = daily.get("time") or []
    iso = today.isoformat()
    if iso not in days:
        raise WaterError("the forecast doesn't cover today")
    i = days.index(iso)

    def val(key: str, idx: int) -> float | None:
        arr = daily.get(key) or []
        return float(arr[idx]) if idx < len(arr) and arr[idx] is not None else None

    rain_today, rain_tomorrow = val("precipitation_sum", i), val("precipitation_sum", i + 1)
    tmax = val("temperature_2m_max", i)
    if rain_today is not None and rain_today >= 5:
        advice = f"Skip watering today: about {rain_today:.0f} mm of rain is forecast."
    elif rain_tomorrow is not None and rain_tomorrow >= 8:
        advice = f"You can skip watering: about {rain_tomorrow:.0f} mm of rain is forecast for tomorrow."
    elif tmax is not None and tmax >= 35:
        advice = f"Hot day ({tmax:.0f}°C). Water deeply in the evening, at the base of the plants."
    else:
        advice = "Check the soil with a finger. Water if the top 2 to 3 cm is dry."
    return {"advice": advice, "rain_today_mm": rain_today, "rain_tomorrow_mm": rain_tomorrow, "max_temp_c": tmax}


def water_tip(lat: float | None, lon: float | None, today: date, fetch=fetch_forecast) -> dict:
    if lat is None or lon is None:
        return {"available": False, "note": "Share your location to get watering tips."}
    key = (round(lat, 2), round(lon, 2), today)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    try:
        result = {"available": True, **decide(fetch(lat, lon), today), "source": "Open-Meteo forecast"}
    except WaterError as e:
        return {"available": False, "note": f"No watering tip right now: {e}."}
    _cache[key] = (time.time(), result)
    return result
