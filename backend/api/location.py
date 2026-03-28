"""
Endpoint de localização + clima — proxy server-side para evitar bloqueios de browser (Safari ITP).
Usa X-Forwarded-For / X-Real-IP para detectar o IP real do usuário (não o do servidor Docker).
"""

import httpx
from fastapi import APIRouter, Request

router = APIRouter()


def _get_client_ip(request: Request) -> str | None:
    """Extrai IP real do usuário dos headers do Nginx reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return None


@router.get("/location")
async def get_location(request: Request):
    """Detecta cidade/país via IP do usuário e retorna clima atual (Open-Meteo)."""
    try:
        client_ip = _get_client_ip(request)
        if not client_ip:
            return {}

        # ipwho.is aceita IP como path param — evita pegar IP do servidor
        geo_url = f"https://ipwho.is/{client_ip}"

        async with httpx.AsyncClient(timeout=5.0) as client:
            geo = await client.get(geo_url)
            data = geo.json()

        if not data.get("success") or not data.get("city"):
            return {}

        result = {
            "city": data["city"],
            "region": data.get("region", ""),
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
                        f"?latitude={lat}&longitude={lon}"
                        f"&current_weather=true"
                        f"&hourly=temperature_2m,relativehumidity_2m,weathercode"
                        f"&forecast_days=1"
                        f"&timezone=auto"
                    )
                    wdata = weather.json()

                    # Clima atual
                    cw = wdata.get("current_weather", {})
                    if cw:
                        result["temp"] = round(cw["temperature"])
                        result["weather_code"] = cw.get("weathercode", 0)
                        result["wind_speed"] = round(cw.get("windspeed", 0))

                    # Previsão das próximas horas (resumo: min/max do dia + umidade)
                    hourly = wdata.get("hourly", {})
                    temps = hourly.get("temperature_2m", [])
                    humidity = hourly.get("relativehumidity_2m", [])
                    if temps:
                        result["temp_min"] = round(min(temps))
                        result["temp_max"] = round(max(temps))
                    if humidity:
                        result["humidity"] = round(sum(humidity) / len(humidity))

            except Exception:
                pass

        return result

    except Exception:
        return {}
