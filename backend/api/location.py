"""
Endpoint de localização + clima — proxy server-side para evitar bloqueios de browser (Safari ITP).
"""

import httpx
from fastapi import APIRouter

router = APIRouter()


@router.get("/location")
async def get_location():
    """Detecta cidade/país via IP e retorna temperatura atual (Open-Meteo)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            geo = await client.get("https://ipwho.is/")
            data = geo.json()

        if not data.get("success") or not data.get("city"):
            return {}

        result = {
            "city": data["city"],
            "country_code": data.get("country_code", ""),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
        }

        lat, lon = result["latitude"], result["longitude"]
        if lat is not None and lon is not None:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    weather = await client.get(
                        f"https://api.open-meteo.com/v1/forecast"
                        f"?latitude={lat}&longitude={lon}&current_weather=true"
                    )
                    wdata = weather.json()
                    cw = wdata.get("current_weather", {})
                    if cw:
                        result["temp"] = round(cw["temperature"])
                        result["weather_code"] = cw.get("weathercode", 0)
            except Exception:
                pass

        return result

    except Exception:
        return {}
