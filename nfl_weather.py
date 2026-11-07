"""Fetch matchup-specific NFL kickoff weather from nflverse schedule + Open-Meteo.

Weather is contextual only: no unvalidated weather coefficients are applied
to scoring or betting probabilities. Venue resolution fails closed rather than
silently selecting a geocoder result in the wrong country.
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SCHEDULE_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"

# nflverse may label international games as location="Neutral". Keep explicit
# venue aliases so a neutral-site game is geocoded at the actual stadium.
INTERNATIONAL_VENUES = {
    "bernabeu": ("Madrid, Spain", "ES"),
    "santiago bernabeu": ("Madrid, Spain", "ES"),
    "tottenham hotspur stadium": ("London, United Kingdom", "GB"),
    "wembley stadium": ("London, United Kingdom", "GB"),
    "allianz arena": ("Munich, Germany", "DE"),
    "estadio azteca": ("Mexico City, Mexico", "MX"),
}


def _get_json(url):
    request = Request(url, headers={"User-Agent": "DougsEliteGameSimulator/1.0"})
    with urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_rows(url):
    request = Request(url, headers={"User-Agent": "DougsEliteGameSimulator/1.0"})
    with urlopen(request, timeout=45) as response:
        return list(csv.DictReader(response.read().decode("utf-8-sig").splitlines()))


def _kickoff(row):
    day = row.get("gameday") or row.get("game_date")
    clock = row.get("gametime") or "13:00"
    if not day:
        raise ValueError("Schedule row is missing gameday.")
    local = datetime.strptime(f"{day} {clock}", "%Y-%m-%d %H:%M")
    return local.replace(tzinfo=ZoneInfo("America/New_York"))


def _resolve_venue_location(venue, schedule_location):
    """Return (search location, expected country code) for the stadium."""
    normalized = (venue or "").strip().lower()
    for alias, location in INTERNATIONAL_VENUES.items():
        if alias in normalized:
            return location
    location = (schedule_location or "").strip()
    if location and location.lower() not in {"neutral", "international", "tbd"}:
        # NFL domestic venues in nflverse schedule data are U.S. locations.
        return location + ", United States", "US"
    raise RuntimeError(
        f"Schedule location is ambiguous for venue {venue!r}; refusing to guess weather coordinates."
    )


def _select_geocoding_result(results, expected_country, venue, location):
    if not results:
        raise RuntimeError(f"No geocoding results for {venue}, {location}.")
    matching = [item for item in results if item.get("country_code") == expected_country]
    if not matching:
        countries = sorted({item.get("country_code", "unknown") for item in results})
        raise RuntimeError(
            f"Geocoder did not return expected country {expected_country} for {venue}, {location}; "
            f"returned countries: {countries}."
        )
    # Prefer a city-level result over an unrelated same-country result.
    location_terms = [part.strip().lower() for part in location.split(",") if part.strip()]
    def score(item):
        fields = " ".join(str(item.get(k, "")) for k in ("name", "admin1", "country")).lower()
        return sum(term in fields for term in location_terms)
    return max(matching, key=score)


def fetch_matchup_weather(home, away, season=None, week=None):
    home, away = home.upper(), away.upper()
    season = season or datetime.now(timezone.utc).year
    rows = _get_rows(SCHEDULE_URL)
    candidates = []
    for row in rows:
        if row.get("home_team") != home or row.get("away_team") != away:
            continue
        if season and str(row.get("season")) != str(season):
            continue
        if week and str(row.get("week")) != str(week):
            continue
        if row.get("game_type") not in {"REG", "POST"}:
            continue
        try:
            kickoff = _kickoff(row)
        except (TypeError, ValueError):
            continue
        candidates.append((kickoff, row))
    if not candidates:
        raise RuntimeError(f"No scheduled nflverse game found for {away} at {home}.")
    now = datetime.now(timezone.utc)
    future = [item for item in candidates if item[0].astimezone(timezone.utc) >= now]
    kickoff, game = min(future or candidates, key=lambda item: abs((item[0].astimezone(timezone.utc)-now).total_seconds()))
    venue = game.get("stadium") or ""
    location, expected_country = _resolve_venue_location(venue, game.get("location"))
    query = ", ".join(part for part in (venue, location) if part)
    geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({
        "name": query, "count": 10, "language": "en", "format": "json"
    })
    geo = _get_json(geo_url)
    results = geo.get("results") or []
    if not results:
        fallback_url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({
            "name": location, "count": 10, "language": "en", "format": "json"
        })
        geo = _get_json(fallback_url)
        results = geo.get("results") or []
    place = _select_geocoding_result(results, expected_country, venue, location)
    forecast_url = "https://api.open-meteo.com/v1/forecast?" + urlencode({
        "latitude": place["latitude"], "longitude": place["longitude"],
        "hourly": "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m",
        "forecast_days": 16, "timezone": "UTC"
    })
    forecast = _get_json(forecast_url)
    hourly = forecast.get("hourly") or {}
    times = hourly.get("time") or []
    if not times:
        raise RuntimeError("Open-Meteo returned no hourly forecast.")
    target = kickoff.astimezone(timezone.utc).replace(tzinfo=None)
    index = min(range(len(times)), key=lambda i: abs((datetime.fromisoformat(times[i])-target).total_seconds()))
    forecast_time = datetime.fromisoformat(times[index]).replace(tzinfo=timezone.utc)
    delta = abs((forecast_time-kickoff.astimezone(timezone.utc)).total_seconds())/60
    if delta > 90:
        raise RuntimeError("No weather forecast close enough to kickoff.")
    def value(field):
        values = hourly.get(field) or []
        return values[index] if index < len(values) else None
    temp, precip, wind, gust = (value(x) for x in (
        "temperature_2m", "precipitation", "wind_speed_10m", "wind_gusts_10m"
    ))
    roof = (game.get("roof") or "").lower()
    is_dome = roof in {"dome", "closed"}
    return {
        "available": True, "home_team": home, "away_team": away,
        "season": game.get("season"), "week": game.get("week"),
        "kickoff": kickoff.isoformat(), "venue": venue, "venue_city": location,
        "schedule_location": game.get("location"), "country_code": place.get("country_code"),
        "roof": game.get("roof"), "surface": game.get("surface"),
        "latitude": place["latitude"], "longitude": place["longitude"],
        "temperature_f": round(float(temp)*9/5+32, 1) if temp is not None else None,
        "precipitation_mm_per_hour": precip,
        "wind_mph": round(float(wind)*0.621371, 1) if wind is not None else None,
        "wind_gust_mph": round(float(gust)*0.621371, 1) if gust is not None else None,
        "forecast_time": forecast_time.isoformat(),
        "forecast_offset_minutes": round(delta, 1),
        "weather_exposure": "INDOOR_OR_CLOSED_ROOF" if is_dome else "OUTDOOR_OR_UNKNOWN",
        "sources": ["nflverse schedule", "Open-Meteo geocoding", "Open-Meteo hourly forecast"],
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_treatment": "Context only; no scoring adjustment until weather coefficients are validated out of sample."
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--season", type=int)
    parser.add_argument("--week", type=int)
    parser.add_argument("--output", default="nfl-weather.json")
    args = parser.parse_args()
    result = fetch_matchup_weather(args.home, args.away, args.season, args.week)
    Path(args.output).write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
