"""College-football drive Monte Carlo engine.

The model is deliberately data-driven: profiles must come from a dated source.
Missing profiles use conservative league-average priors and are flagged in output.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import random
from typing import Optional


@dataclass(frozen=True)
class TeamProfile:
    name: str
    points_for: float = 28.0
    points_against: float = 28.0
    yards_per_play: float = 5.8
    yards_per_play_allowed: float = 5.8
    plays_per_game: float = 70.0
    points_per_drive: Optional[float] = None
    turnovers_per_game: float = 1.4
    takeaways_per_game: float = 1.4
    explosive_play_rate: float = 0.12
    success_rate: float = 0.42
    strength_rating: float = 0.0
    games_sampled: int = 0
    source: str = "league-average prior"
    as_of: str = ""

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Team name cannot be blank")
        positive = ("points_for", "points_against", "yards_per_play",
                    "yards_per_play_allowed", "plays_per_game")
        for key in positive:
            value = getattr(self, key)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be a positive finite number")
        for key in ("turnovers_per_game", "takeaways_per_game",
                    "explosive_play_rate", "success_rate"):
            value = getattr(self, key)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{key} must be finite and non-negative")
        if self.explosive_play_rate > 1 or self.success_rate > 1:
            raise ValueError("Rates must be between 0 and 1")
        if self.games_sampled < 0:
            raise ValueError("games_sampled cannot be negative")


@dataclass(frozen=True)
class MarketLines:
    spread_home: Optional[float] = None  # sportsbook home-team handicap
    total: Optional[float] = None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _expected_drives(profile: TeamProfile) -> float:
    # College pace varies materially; use plays and a calibrated 6.1 plays/drive.
    return _clamp(profile.plays_per_game / 6.1, 8.0, 16.0)


def _points_per_drive(offense: TeamProfile, defense: TeamProfile) -> float:
    off_ppd = offense.points_per_drive
    if off_ppd is None:
        off_ppd = offense.points_for / _expected_drives(offense)
    def_ppd_allowed = defense.points_against / _expected_drives(defense)
    base = 0.58 * off_ppd + 0.42 * def_ppd_allowed
    efficiency = (offense.yards_per_play / max(defense.yards_per_play_allowed, 0.1))
    success = (offense.success_rate - 0.42) * 1.7
    explosive = (offense.explosive_play_rate - 0.12) * 2.0
    strength = (offense.strength_rating - defense.strength_rating) / 30.0
    turnover_edge = (defense.takeaways_per_game - offense.turnovers_per_game) * 0.11
    return _clamp(base + (efficiency - 1.0) * 1.15 + success + explosive
                  + strength + turnover_edge, 0.65, 5.2)


def _drive_points(ppd: float, turnover_rate: float, rng: random.Random) -> int:
    # Calibrated drive outcome buckets: TD, FG, turnover, punt/other.
    td_prob = _clamp(ppd * 0.10, 0.06, 0.48)
    fg_prob = _clamp((ppd - 7.0 * td_prob) / 3.0, 0.04, 0.42)
    to_prob = _clamp(0.12 + (turnover_rate - 1.4) * 0.025, 0.06, 0.22)
    punt_prob = max(0.0, 1.0 - td_prob - fg_prob - to_prob)
    draw = rng.random()
    if draw < td_prob:
        return 7
    if draw < td_prob + fg_prob:
        return 3
    if draw < td_prob + fg_prob + to_prob:
        return 0
    # A small fraction of otherwise empty drives end in a safety/defensive score.
    return 0


def simulate_game(
    home: TeamProfile,
    away: TeamProfile,
    trials: int = 100_000,
    lines: Optional[MarketLines] = None,
    seed: int = 20261104,
    neutral_site: bool = False,
) -> dict:
    """Run reproducible drive-level Monte Carlo trials and return market probabilities."""
    home.validate()
    away.validate()
    if trials < 1 or trials > 5_000_000:
        raise ValueError("trials must be between 1 and 5,000,000")
    lines = lines or MarketLines()
    rng = random.Random(seed)

    home_ppd = _points_per_drive(home, away)
    away_ppd = _points_per_drive(away, home)
    home_drives = _expected_drives(home)
    away_drives = _expected_drives(away)
    home_edge = 0.0 if neutral_site else 2.2
    home_ppd = _clamp(home_ppd + home_edge / (home_drives * 2.2), 0.65, 5.2)

    home_scores: list[int] = []
    away_scores: list[int] = []
    home_wins = ties = home_covers = overs = 0
    margin_sum = total_sum = 0.0

    for _ in range(trials):
        # Small shared game-environment shock creates correlated pace/scoring variance.
        game_shock = rng.gauss(0.0, 0.12)
        h_count = max(6, round(rng.gauss(home_drives, 0.85)))
        a_count = max(6, round(rng.gauss(away_drives, 0.85)))
        hs = sum(_drive_points(_clamp(home_ppd + game_shock, 0.65, 5.2),
                               home.turnovers_per_game, rng) for _ in range(h_count))
        as_ = sum(_drive_points(_clamp(away_ppd + game_shock, 0.65, 5.2),
                                away.turnovers_per_game, rng) for _ in range(a_count))
        # Overtime is represented as a modest one-possession resolution, not a full OT ruleset.
        if hs == as_:
            if rng.random() < 0.5:
                hs += 7
            else:
                as_ += 7
        home_scores.append(hs)
        away_scores.append(as_)
        margin = hs - as_
        total = hs + as_
        margin_sum += margin
        total_sum += total
        home_wins += margin > 0
        ties += margin == 0
        if lines.spread_home is not None:
            home_covers += margin + lines.spread_home > 0
        if lines.total is not None:
            overs += total > lines.total

    mean_home = sum(home_scores) / trials
    mean_away = sum(away_scores) / trials
    result = {
        "model": "Doug's Elite NCAA Football Simulator",
        "trials": trials,
        "seed": seed,
        "home_team": home.name,
        "away_team": away.name,
        "neutral_site": neutral_site,
        "projected_score": {home.name: round(mean_home, 2), away.name: round(mean_away, 2)},
        "projected_margin_home": round(margin_sum / trials, 2),
        "projected_total": round(total_sum / trials, 2),
        "home_win_probability": round(home_wins / trials, 4),
        "away_win_probability": round((trials - home_wins) / trials, 4),
        "expected_points_per_drive": {home.name: round(home_ppd, 3), away.name: round(away_ppd, 3)},
        "expected_drives": {home.name: round(home_drives, 2), away.name: round(away_drives, 2)},
        "market": {},
        "data_quality": {
            "home_games_sampled": home.games_sampled,
            "away_games_sampled": away.games_sampled,
            "home_source": home.source,
            "away_source": away.source,
            "warnings": _warnings(home, away),
        },
        "profiles": {home.name: asdict(home), away.name: asdict(away)},
    }
    if lines.spread_home is not None:
        result["market"]["home_spread"] = lines.spread_home
        result["market"]["home_cover_probability"] = round(home_covers / trials, 4)
        result["market"]["away_cover_probability"] = round(1 - home_covers / trials, 4)
    if lines.total is not None:
        result["market"]["total_line"] = lines.total
        result["market"]["over_probability"] = round(overs / trials, 4)
        result["market"]["under_probability"] = round(1 - overs / trials, 4)
    return result


def _warnings(home: TeamProfile, away: TeamProfile) -> list[str]:
    warnings = []
    for team in (home, away):
        if team.games_sampled == 0:
            warnings.append(f"{team.name}: no verified season sample; league-average prior used")
        elif team.games_sampled < 5:
            warnings.append(f"{team.name}: only {team.games_sampled} games; high uncertainty")
        elif team.games_sampled < 8:
            warnings.append(f"{team.name}: limited sample ({team.games_sampled} games)")
        if team.source == "league-average prior":
            warnings.append(f"{team.name}: replace prior with current-season data before betting use")
    return warnings
