"""Local functions that Claude can call via JSON blocks."""

import logging
import urllib.request
import urllib.parse
import json

logger = logging.getLogger(__name__)

FUNCTION_REGISTRY = {}


def register(name, description, parameters):
    """Decorator to register a function Claude can call."""
    def decorator(fn):
        FUNCTION_REGISTRY[name] = {
            "function": fn,
            "description": description,
            "parameters": parameters,
        }
        return fn
    return decorator


def call(name, args):
    """Call a registered function by name with the given args dict."""
    if name not in FUNCTION_REGISTRY:
        return {"error": f"Unknown function: {name}"}
    try:
        return FUNCTION_REGISTRY[name]["function"](**args)
    except Exception as e:
        return {"error": str(e)}


def get_prompt_description():
    """Generate a description of available functions for the system prompt."""
    lines = []
    for name, info in FUNCTION_REGISTRY.items():
        params = ", ".join(
            f'{p["name"]} ({p["type"]}): {p["description"]}'
            for p in info["parameters"]
        )
        lines.append(f'- {name}({params}): {info["description"]}')
    return "\n".join(lines)


# --- Registered functions ---


@register(
    name="get_weather",
    description="Get the current weather for a location",
    parameters=[
        {"name": "location", "type": "string", "description": "City or location name"},
    ],
)
def get_weather(location):
    """Get real weather using Open-Meteo (no API key needed)."""
    try:
        # Geocode the location name to lat/lon (use just the city name)
        city = location.split(",")[0].strip()
        geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode({
            "name": city, "count": 1
        })
        with urllib.request.urlopen(geo_url) as resp:
            geo = json.loads(resp.read())

        if "results" not in geo or not geo["results"]:
            return {"error": f"Could not find location: {location}"}

        place = geo["results"][0]
        lat, lon = place["latitude"], place["longitude"]
        name = place.get("name", location)

        # Fetch current weather
        weather_url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "temperature_unit": "celsius",
        })
        with urllib.request.urlopen(weather_url) as resp:
            weather = json.loads(resp.read())

        current = weather["current"]
        # Map WMO weather codes to descriptions
        code = current["weather_code"]
        conditions = {
            0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
            45: "foggy", 48: "depositing rime fog",
            51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
            61: "slight rain", 63: "moderate rain", 65: "heavy rain",
            71: "slight snow", 73: "moderate snow", 75: "heavy snow",
            80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
            95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
        }
        return {
            "location": name,
            "temperature": current["temperature_2m"],
            "humidity": current["relative_humidity_2m"],
            "condition": conditions.get(code, f"code {code}"),
            "wind_speed": current["wind_speed_10m"],
        }
    except Exception as e:
        logger.error("Weather lookup failed: %s", e)
        return {"error": str(e)}
