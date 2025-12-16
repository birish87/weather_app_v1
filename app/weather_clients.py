"""
Weather clients.

We intentionally separate API logic from FastAPI endpoints:
- easier to test in isolation
- cleaner main.py
- avoids duplicating request logic for CRUD and UI use cases
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timezone, timedelta
from typing import Any, Dict, List, Tuple
from collections import Counter, defaultdict
import httpx
import re
from typing import Optional


@dataclass(frozen=True)
class ResolvedLocation:
    """
    Minimal resolved location object produced by geocoding.
    """
    name: str
    country: str
    state: str
    lat: float
    lon: float


class WeatherError(RuntimeError):
    """Raised for user-facing weather lookup failures."""
    pass


class OpenWeatherClient:
    """
    OpenWeatherMap wrapper.

    Endpoints used:
    - Geocoding:
        /geo/1.0/direct?q=...&limit=5&appid=KEY
    - Current weather:
        /data/2.5/weather?lat=...&lon=...&units=imperial&appid=KEY
    - 5-day forecast (3-hour increments):
        /data/2.5/forecast?lat=...&lon=...&units=imperial&appid=KEY

    We use units=imperial for display in the UI; you can swap to metric easily.
    """

    def __init__(self, api_key: str, timeout_s: float = 10.0):
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.base = "https://api.openweathermap.org"

    async def geocode(self, query: str) -> ResolvedLocation:
        """
        Resolve a user-provided location string into a (name/state/country/lat/lon).

        Supported input formats (checked in this order):

        1) Coordinates: "40.7128,-74.0060"
           - We validate bounds and then reverse-geocode to get a human-friendly label.

        2) ZIP code: "10001" or "10001-1234" or "10001,US"
           - Uses OpenWeather's ZIP geocoding endpoint, which is more reliable than "direct"
             geocoding for ZIPs. Defaults to US if no country is provided.

        3) Place name: "Austin, TX" or "Paris, FR"
           - Uses OpenWeather direct geocoding; we select the top match.
        """
        # raw = query.strip()
        raw = query.strip().strip("'\"")

        # ---------------------------------------------------------------------
        # 1) Coordinate detection: "lat,lon" (optional whitespace)
        # ---------------------------------------------------------------------
        coord_match = re.fullmatch(
            r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*",
            raw,
        )
        if coord_match:
            lat = float(coord_match.group(1))
            lon = float(coord_match.group(2))

            # Validate coordinate ranges
            if not (-90.0 <= lat <= 90.0):
                raise WeatherError("Invalid latitude. Must be between -90 and 90.")
            if not (-180.0 <= lon <= 180.0):
                raise WeatherError("Invalid longitude. Must be between -180 and 180.")

            # Reverse geocode: lat/lon -> best human-friendly place name/state/country
            params = {"lat": lat, "lon": lon, "limit": 1, "appid": self.api_key}
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                r = await client.get(f"{self.base}/geo/1.0/reverse", params=params)

            if r.status_code != 200:
                raise WeatherError(f"Reverse geocoding failed ({r.status_code}): {r.text}")

            results = r.json() or []
            if results:
                best = results[0]
                return ResolvedLocation(
                    name=best.get("name", "Current Location"),
                    state=best.get("state", ""),
                    country=best.get("country", ""),
                    lat=lat,
                    lon=lon,
                )

            # If reverse geocoding returns no results, still return valid coordinates
            return ResolvedLocation(
                name="Current Location",
                state="",
                country="",
                lat=lat,
                lon=lon,
            )

        # ---------------------------------------------------------------------
        # 2) ZIP detection: "12345" or "12345-6789" optionally ",CC" (country code)
        #    Examples: "10001", "10001-1234", "10001,US", "10001-1234,US"
        # ---------------------------------------------------------------------
        zip_match = re.fullmatch(
            r"(?i)\s*(\d{5})(?:-\d{4})?\s*(?:,\s*([a-z]{2}))?\s*",
            raw,
        )
        if zip_match:
            zip5 = zip_match.group(1)
            country = (zip_match.group(2) or "US").upper()

            params = {"zip": f"{zip5},{country}", "appid": self.api_key}
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                r = await client.get(f"{self.base}/geo/1.0/zip", params=params)

            if r.status_code != 200:
                raise WeatherError(f"ZIP geocoding failed ({r.status_code}): {r.text}")

            data = r.json()
            return ResolvedLocation(
                name=data.get("name", raw),
                # ZIP endpoint returns country, but typically does NOT include state reliably
                state="",
                country=data.get("country", country),
                lat=float(data["lat"]),
                lon=float(data["lon"]),
            )
        # ---------------------------------------------------------------------
        # 2b) International postal codes (must include country code)
        # Accept:
        #   A) "SW1A 1AA, London, GB"
        #   B) "10115, DE" i.e., Berlin Germany
        # Won't work:
        #   C) "SW1A 1AA, GB"
        # ---------------------------------------------------------------------

        # B) "POSTAL, CITY, CC"
        postal_city_cc = re.fullmatch(
            r"(?i)\s*([A-Z0-9][A-Z0-9 \-]{2,12})\s*,\s*([^,]{2,64})\s*,\s*([A-Z]{2})\s*",
            raw,
        )
        if postal_city_cc:
            postal = postal_city_cc.group(1).strip()
            city = postal_city_cc.group(2).strip()
            country = postal_city_cc.group(3).upper()

            # Try a few query variants (OpenWeather is picky)
            candidates = [
                f"{postal}, {city}, {country}",
                f"{city}, {country} {postal}",
                f"{postal}, {country}",
            ]

            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                for q in candidates:
                    r = await client.get(f"{self.base}/geo/1.0/direct",
                                         params={"q": q, "limit": 5, "appid": self.api_key})
                    if r.status_code != 200:
                        continue
                    results = r.json() or []
                    if results:
                        best = results[0]
                        return ResolvedLocation(
                            name=best.get("name", raw),
                            state=best.get("state", ""),
                            country=best.get("country", country),
                            lat=float(best["lat"]),
                            lon=float(best["lon"]),
                        )

            raise WeatherError(
                "Postal code not found for that city/country. Try 'SW1A 1AA, GB' "
                "or verify spelling/country code."
            )

        # A) "POSTAL, CC"
        postal_cc = re.fullmatch(
            r"(?i)\s*([A-Z0-9][A-Z0-9 \-]{2,12})\s*,\s*([A-Z]{2})\s*",
            raw,
        )
        if postal_cc:
            postal = postal_cc.group(1).strip()
            country = postal_cc.group(2).upper()

            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                # try a couple variants
                for q in (f"{postal}, {country}", f"{postal} {country}"):
                    r = await client.get(f"{self.base}/geo/1.0/direct",
                                         params={"q": q, "limit": 5, "appid": self.api_key})
                    if r.status_code != 200:
                        continue
                    results = r.json() or []
                    if results:
                        best = results[0]
                        return ResolvedLocation(
                            name=best.get("name", raw),
                            state=best.get("state", ""),
                            country=best.get("country", country),
                            lat=float(best["lat"]),
                            lon=float(best["lon"]),
                        )

            raise WeatherError(
                "Postal code not found. Try adding the city too (e.g., 'SW1A 1AA, London, GB') "
                "or confirm the country code."
            )

        # ---------------------------------------------------------------------
        # 3) Default: place / city direct geocoding ("Austin, TX", "Paris, FR")
        # ---------------------------------------------------------------------
        params = {"q": raw, "limit": 5, "appid": self.api_key}
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.get(f"{self.base}/geo/1.0/direct", params=params)

        if r.status_code != 200:
            raise WeatherError(f"Geocoding failed ({r.status_code}): {r.text}")

        results = r.json() or []
        if not results:
            raise WeatherError(
                "Location not found. Try a more specific query "
                "(e.g., 'Paris, FR', 'Austin, TX', '10001,US', or '40.7128,-74.0060')."
            )

        best = results[0]
        return ResolvedLocation(
            name=best.get("name", raw),
            state=best.get("state", ""),
            country=best.get("country", ""),
            lat=float(best["lat"]),
            lon=float(best["lon"]),
        )

    async def current_weather(self, lat: float, lon: float, units: str = "imperial") -> Dict[str, Any]:
        """
        Retrieves current weather conditions for a lat/lon.
        """
        params = {"lat": lat, "lon": lon, "units": units, "appid": self.api_key}
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.get(f"{self.base}/data/2.5/weather", params=params)

        if r.status_code != 200:
            raise WeatherError(f"Current weather failed ({r.status_code}): {r.text}")
        return r.json()

    async def forecast_5day_3h(self, lat: float, lon: float, units: str = "imperial") -> Dict[str, Any]:
        """
        Retrieves the 5-day forecast in 3-hour increments.
        We later summarize this into one card per day (min/max + icon).
        """
        params = {"lat": lat, "lon": lon, "units": units, "appid": self.api_key}
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.get(f"{self.base}/data/2.5/forecast", params=params)

        if r.status_code != 200:
            raise WeatherError(f"Forecast failed ({r.status_code}): {r.text}")
        return r.json()

    @staticmethod
    def summarize_to_5_days(forecast_3h: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        OpenWeather forecast returns ~40 data points (3-hour steps).
        The UI requirement wants a "5-day forecast", which is best shown as daily cards.

        Strategy:
        - Group items by local date (using city timezone offset)
        - For each day:
          - temp min over all steps
          - temp max over all steps
          - choose the most frequent (icon, description) pair
        """
        city = forecast_3h.get("city", {})
        tz_offset = int(city.get("timezone", 0))  # seconds offset from UTC
        items = forecast_3h.get("list", [])

        def local_day(dt_utc: int) -> date:
            # Convert forecast timestamp (UTC) into the city's local date
            return datetime.fromtimestamp(dt_utc + tz_offset, tz=timezone.utc).date()

        grouped: Dict[date, List[Dict[str, Any]]] = {}
        for item in items:
            d = local_day(int(item["dt"]))
            grouped.setdefault(d, []).append(item)

        days: List[Dict[str, Any]] = []
        for d in sorted(grouped.keys())[:5]:
            steps = grouped[d]

            # percent chance of precipitation for the day
            pops = []
            for x in steps:
                # pop is 0..1, may not exist on all steps
                if "pop" in x and x["pop"] is not None:
                    pops.append(float(x["pop"]))

            pop_max = max(pops) if pops else None  # 0..1
            pop_pct = round(pop_max * 100) if pop_max is not None else None

            temps = [
                float(x["main"]["temp"])
                for x in steps
                if "main" in x and "temp" in x["main"]
            ]
            tmin = min(temps) if temps else None
            tmax = max(temps) if temps else None

            # Find most frequent icon/description for that day
            counts: Dict[Tuple[str, str], int] = {}
            for x in steps:
                w = (x.get("weather") or [{}])[0]
                icon = w.get("icon", "")
                desc = w.get("description", "")
                counts[(icon, desc)] = counts.get((icon, desc), 0) + 1

            (icon, desc) = max(counts.items(), key=lambda kv: kv[1])[0] if counts else ("", "")

            days.append({
                "date": d.isoformat(),  # keep existing ISO date
                "dow": d.strftime("%a"),  # e.g., "Fri"
                "date_display": d.strftime("%b %d, %Y"),  # e.g., "Dec 14, 2025"
                "tmin": tmin,
                "tmax": tmax,
                "icon": icon,
                "description": desc,
                "pop_max": pop_max,
                "pop_pct": pop_pct,
            })

        return days


class OpenMeteoClient:
    """
    Open-Meteo is used ONLY for Assessment 2's date-range daily min/max temperatures.

    Why Open-Meteo?
    - No API key required
    - Provides daily min/max directly for a date window
    - Easy to store in DB
    """

    def __init__(self, timeout_s: float = 10.0):
        self.timeout_s = timeout_s
        self.base = "https://api.open-meteo.com/v1/forecast"

    async def daily_temps(self, lat: float, lon: float, start: date, end: date) -> List[Dict[str, Any]]:
        """
        Fetch daily min/max temps (Celsius by default from Open-Meteo).
        Store exactly what is returned (date, min, max) to keep it simple.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
        }

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.get(self.base, params=params)

        if r.status_code != 200:
            raise WeatherError(f"Open-Meteo daily temps failed ({r.status_code}): {r.text}")

        data = r.json()
        daily = data.get("daily") or {}
        dates = daily.get("time") or []
        tmax = daily.get("temperature_2m_max") or []
        tmin = daily.get("temperature_2m_min") or []

        out: List[Dict[str, Any]] = []
        for i in range(min(len(dates), len(tmax), len(tmin))):
            out.append({"date": dates[i], "tmax": float(tmax[i]), "tmin": float(tmin[i])})

        if not out:
            raise WeatherError("No daily temperatures returned for that range.")

        return out
