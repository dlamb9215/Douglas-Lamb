"""Optional venue-based kickoff weather context from CFBD and Open-Meteo.

Weather is reported as context only. It is not used to alter model probabilities
until a separately validated weather calibration is available.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .data.refresh import api_get


def _get_open_meteo(latitude: float, longitude: float) -> dict:
    query = urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m",
        "forecast_days": 16,
        "timezone": "UTC",
    })
    request = Request(
        f"https://api.open-meteo.com/v1/forecast?{query}",
        headers={"Accept": "application/json", "User-Agent": "DougsEliteNCAASimulator/1.0"},
    )
    with urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("hourly"), dict):
        raise RuntimeError("Open-Meteo returned an unexpected forecast response")
    return payload


def fetch_game_weather(year: int, home: str, away: str, api_key: str,
                       kickoff: str | None = None) -> dict:
    games = api_get("/games", {
        "year": year, "seasonType": "regular", "home": home, "away": away,
        "classification": "fbs",
    }, api_key)
    if not isinstance(games, list):
        raise RuntimeError("CFBD schedule endpoint returned an unexpected response")
    now = datetime.now(timezone.utc)
    candidates = []
    for game in games:
        if str(game.get("homeTeam", "")).casefold() != home.casefold():
            continue
        if str(game.get("awayTeam", "")).casefold() != away.casefold():
            continue
        start_raw = game.get("startDate")
        if not start_raw:
            continue
        try:
            start = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        start = start.astimezone(timezone.utc)
        if kickoff:
            target = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
            if target.tzinfo is None:
                raise ValueError("kickoff must include a timezone")
            if abs((start - target.astimezone(timezone.utc)).total_seconds()) > 48 * 3600:
                continue
        elif start < now:
            continue
        candidates.append((start, game))
    if not candidates:
        raise RuntimeError("No matching scheduled game found for weather lookup")
    start, game = min(candidates, key=lambda pair: pair[0])
    venue_id = game.get("venueId")
    if venue_id is None:
        raise RuntimeError("CFBD schedule did not include a venue ID")
    venues = api_get("/venues", {}, api_key)
    venue = next((v for v in venues if str(v.get("id")) == str(venue_id)), None) if isinstance(venues, list) else None
    if not venue:
        raise RuntimeError("CFBD venue lookup did not find the scheduled venue")
    latitude, longitude = venue.get("latitude"), venue.get("longitude")
    if latitude is None or longitude is None:
        raise RuntimeError("CFBD venue coordinates are unavailable")
    forecast = _get_open_meteo(float(latitude), float(longitude))
    hourly = forecast["hourly"]
    times = hourly.get("time", [])
    if not times:
        raise RuntimeError("Open-Meteo returned no hourly forecast timestamps")
    target_index = min(range(len(times)), key=lambda i: abs(
        (datetime.fromisoformat(times[i]).replace(tzinfo=timezone.utc) - start).total_seconds()
    ))
    forecast_time = datetime.fromisoformat(times[target_index]).replace(tzinfo=timezone.utc)
    delta_minutes = abs((forecast_time - start).total_seconds()) / 60
    if delta_minutes > 90:
        raise RuntimeError("No hourly weather forecast close enough to kickoff")
    def at(field):
        values = hourly.get(field, [])
        return values[target_index] if target_index < len(values) else None
    temp_c = at("temperature_2m")
    precip_mm = at("precipitation")
    wind_kmh = at("wind_speed_10m")
    gust_kmh = at("wind_gusts_10m")
    return {
        "available": True,
        "home_team": home,
        "away_team": away,
        "kickoff": start.isoformat(),
        "venue": venue.get("name", ""),
        "latitude": float(latitude),
        "longitude": float(longitude),
        "forecast_time": forecast_time.isoformat(),
        "forecast_time_offset_minutes": round(delta_minutes, 1),
        "temperature_f": round(float(temp_c) * 9 / 5 + 32, 1) if temp_c is not None else None,
        "precipitation_mm_per_hour": precip_mm,
        "wind_mph": round(float(wind_kmh) * 0.621371, 1) if wind_kmh is not None else None,
        "wind_gust_mph": round(float(gust_kmh) * 0.621371, 1) if gust_kmh is not None else None,
        "sources": ["CollegeFootballData schedule and venue", "Open-Meteo hourly forecast"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "model_treatment": "Context only; weather is not applied to probabilities because calibrated coefficients are not yet available.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch kickoff weather context for an NCAA matchup")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--kickoff", default=None)
    parser.add_argument("--output", default="weather.json")
    args = parser.parse_args()
    key = os.environ.get("CFBD_API_KEY", "").strip()
    if not key:
        raise SystemExit("CFBD_API_KEY is missing.")
    result = fetch_game_weather(args.year, args.home, args.away, key, args.kickoff)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
