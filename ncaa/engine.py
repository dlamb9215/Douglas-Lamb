"""College-football drive Monte Carlo engine.

The model is deliberately data-driven: profiles must come from a dated source.
Missing profiles use conservative league-average priors and are flagged in output.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields as dataclass_fields
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
    total_yards_per_game: float = 0.0
    total_yards_allowed_per_game: float = 0.0
    plays_per_game: float = 70.0
    pass_yards_per_game: float = 0.0
    rush_yards_per_game: float = 0.0
    pass_attempts_per_game: float = 0.0
    completions_per_game: float = 0.0
    completion_pct: float = 0.0
    yards_per_pass_attempt: float = 0.0
    pass_tds_per_game: float = 0.0
    interceptions_per_game: float = 0.0
    pass_first_downs_per_game: float = 0.0
    rush_attempts_per_game: float = 0.0
    yards_per_carry: float = 0.0
    rush_tds_per_game: float = 0.0
    rush_first_downs_per_game: float = 0.0
    pass_yards_allowed_per_game: float = 0.0
    plays_allowed_per_game: float = 0.0
    pass_first_downs_allowed_per_game: float = 0.0
    rush_first_downs_allowed_per_game: float = 0.0
    opponent_pass_attempts_per_game: float = 0.0
    opponent_completions_per_game: float = 0.0
    opponent_yards_per_completion: float = 0.0
    opponent_yards_per_pass_attempt_allowed: float = 0.0
    rush_yards_allowed_per_game: float = 0.0
    opponent_rush_attempts_per_game: float = 0.0
    opponent_yards_per_carry_allowed: float = 0.0
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
        nonnegative = {
            field.name for field in dataclass_fields(self)
            if field.name not in {"name", "source", "as_of", "points_per_drive",
                                  "points_for", "points_against", "yards_per_play",
                                  "yards_per_play_allowed", "plays_per_game", "strength_rating"}
        }
        for key in nonnegative:
            value = getattr(self, key)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{key} must be finite and non-negative")
        for key in ("completion_pct", "explosive_play_rate", "success_rate"):
            value = getattr(self, key)
            if value > 1:
                raise ValueError(f"{key} must be between 0 and 1")
        if self.points_per_drive is not None and (
            not math.isfinite(self.points_per_drive) or self.points_per_drive <= 0
        ):
            raise ValueError("points_per_drive must be positive and finite when supplied")
        if self.games_sampled < 0:
            raise ValueError("games_sampled cannot be negative")
        if self.completions_per_game > self.pass_attempts_per_game and self.pass_attempts_per_game > 0:
            raise ValueError("completions_per_game cannot exceed pass_attempts_per_game")


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
    pass_edge = 0.0
    if offense.yards_per_pass_attempt > 0 and defense.opponent_yards_per_pass_attempt_allowed > 0:
        pass_edge = _clamp((offense.yards_per_pass_attempt - defense.opponent_yards_per_pass_attempt_allowed) / 8.0, -0.18, 0.18)
    rush_edge = 0.0
    if offense.yards_per_carry > 0 and defense.opponent_yards_per_carry_allowed > 0:
        rush_edge = _clamp((offense.yards_per_carry - defense.opponent_yards_per_carry_allowed) / 6.0, -0.18, 0.18)
    success = (offense.success_rate - 0.42) * 1.7
    explosive = (offense.explosive_play_rate - 0.12) * 2.0
    strength = (offense.strength_rating - defense.strength_rating) / 30.0
    return _clamp(base + (efficiency - 1.0) * 1.15 + pass_edge * 0.45 + rush_edge * 0.35 + success + explosive
                  + strength, 0.65, 5.2)


def _drive_turnover_probability(offense: TeamProfile, defense: TeamProfile) -> float:
    """Blend observed giveaways and opponent takeaways into a per-drive risk."""
    drives = max(_expected_drives(offense), 1.0)
    events_per_game = 0.5 * (
        offense.turnovers_per_game + defense.takeaways_per_game
    )
    return _clamp(events_per_game / drives, 0.035, 0.24)


def _drive_points(ppd: float, turnover_probability: float,
                  rng: random.Random) -> int:
    """Sample a drive result from TD, field-goal, turnover and empty-drive outcomes."""
    td_prob = _clamp(ppd * 0.10, 0.06, 0.48)
    fg_prob = _clamp((ppd - 7.0 * td_prob) / 3.0, 0.04, 0.42)
    to_prob = _clamp(turnover_probability, 0.035, 0.24)
    # Turnovers replace productive possessions. Scale scoring frequency around
    # a neutral 12% per-drive turnover baseline; this coefficient is a model
    # assumption to be evaluated and recalibrated against the forecast ledger.
    scoring_scale = _clamp(1.0 - (to_prob - 0.12) * 1.5, 0.75, 1.12)
    td_prob *= scoring_scale
    fg_prob *= scoring_scale
    # Preserve a valid mutually exclusive probability distribution.
    scoring_total = td_prob + fg_prob
    scoring_cap = 1.0 - to_prob
    if scoring_total > scoring_cap:
        scale = scoring_cap / scoring_total
        td_prob *= scale
        fg_prob *= scale
    draw = rng.random()
    if draw < td_prob:
        return 7
    if draw < td_prob + fg_prob:
        return 3
    return 0


def _simulate_overtime(home_ppd: float, away_ppd: float,
                       home_to_probability: float,
                       away_to_probability: float,
                       rng: random.Random) -> tuple[int, int, int]:
    """Resolve ties with alternating college-style possessions, then conversion rounds.

    This is a transparent overtime approximation rather than a rules-exact
    play-by-play implementation. After two possession rounds, teams alternate
    modeled two-point attempts to avoid the old arbitrary seven-point tiebreak.
    """
    home_total = away_total = 0
    for round_number in range(1, 13):
        if round_number <= 2:
            home_td = _clamp(0.48 + (home_ppd - 2.5) * 0.055, 0.28, 0.68)
            away_td = _clamp(0.48 + (away_ppd - 2.5) * 0.055, 0.28, 0.68)
            home_fg = _clamp(0.22 + (home_ppd - 2.5) * 0.015, 0.10, 0.32)
            away_fg = _clamp(0.22 + (away_ppd - 2.5) * 0.015, 0.10, 0.32)
            def ot_score(td, fg, to):
                draw = rng.random()
                if draw < td:
                    return 7
                if draw < td + fg:
                    return 3
                if draw < td + fg + to * 0.65:
                    return 0
                return 0
            home_points = ot_score(home_td, home_fg, home_to_probability)
            away_points = ot_score(away_td, away_fg, away_to_probability)
        else:
            home_two = _clamp(0.43 + (home_ppd - 2.5) * 0.045, 0.28, 0.62)
            away_two = _clamp(0.43 + (away_ppd - 2.5) * 0.045, 0.28, 0.62)
            home_points = 2 if rng.random() < home_two else 0
            away_points = 2 if rng.random() < away_two else 0
        home_total += home_points
        away_total += away_points
        if home_points != away_points:
            return home_total, away_total, round_number
    # Extremely unlikely pathological tie after conversion rounds.
    return (home_total + 2, away_total, 12) if rng.random() < 0.5 else (home_total, away_total + 2, 12)


def _simulate_first_half(home_ppd: float, away_ppd: float,
                         home_turnovers: float, away_turnovers: float,
                         rng: random.Random) -> tuple[int, int, int, int]:
    """Clock-limited 30-minute half using alternating drive durations.

    This is a drive-duration approximation, not a play-by-play clock simulator.
    """
    remaining = 30.0 * 60.0
    home_score = away_score = home_drives = away_drives = 0
    home_ball = rng.random() < 0.5
    while remaining > 0:
        duration = _clamp(rng.lognormvariate(math.log(150.0), 0.35), 55.0, 330.0)
        if duration > remaining:
            break
        if home_ball:
            home_score += _drive_points(home_ppd, home_turnovers, rng)
            home_drives += 1
        else:
            away_score += _drive_points(away_ppd, away_turnovers, rng)
            away_drives += 1
        remaining -= duration
        home_ball = not home_ball
    return home_score, away_score, home_drives, away_drives


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

    raw_home_ppd = _points_per_drive(home, away)
    raw_away_ppd = _points_per_drive(away, home)
    home_sample_weight = home.games_sampled / (home.games_sampled + 4.0) if home.games_sampled else 0.0
    away_sample_weight = away.games_sampled / (away.games_sampled + 4.0) if away.games_sampled else 0.0
    # Empirical-Bayes-style shrinkage toward a conservative FBS/FCS scoring prior.
    # The prior is deliberately disclosed; weights rise with completed-game sample.
    home_ppd = 2.50 + (raw_home_ppd - 2.50) * home_sample_weight
    away_ppd = 2.50 + (raw_away_ppd - 2.50) * away_sample_weight
    home_drives = _expected_drives(home)
    away_drives = _expected_drives(away)
    home_to_probability = _drive_turnover_probability(home, away)
    away_to_probability = _drive_turnover_probability(away, home)
    home_edge = 0.0 if neutral_site else 2.2
    home_ppd = _clamp(home_ppd + home_edge / home_drives, 0.65, 5.2)

    home_scores: list[int] = []
    away_scores: list[int] = []
    home_first_scores: list[int] = []
    away_first_scores: list[int] = []
    home_wins = ties = home_covers = home_cover_pushes = overs = total_pushes = 0
    margin_sum = total_sum = first_home_sum = first_away_sum = 0.0
    first_half_home_drives = first_half_away_drives = 0

    for _ in range(trials):
        # Small shared game-environment shock creates correlated pace/scoring variance.
        game_shock = rng.gauss(0.0, 0.12)
        home_uncertainty = 0.10 + 0.42 / math.sqrt(max(home.games_sampled, 1))
        away_uncertainty = 0.10 + 0.42 / math.sqrt(max(away.games_sampled, 1))
        home_game_ppd = _clamp(home_ppd + game_shock + rng.gauss(0.0, home_uncertainty), 0.65, 5.2)
        away_game_ppd = _clamp(away_ppd + game_shock + rng.gauss(0.0, away_uncertainty), 0.65, 5.2)
        pace_shock = rng.gauss(0.0, 0.45)
        h_count = max(6, round(rng.gauss(home_drives + pace_shock, 0.85)))
        a_count = max(6, round(rng.gauss(away_drives + pace_shock, 0.85)))
        h_outcomes = [_drive_points(home_game_ppd, home_to_probability, rng) for _ in range(h_count)]
        a_outcomes = [_drive_points(away_game_ppd, away_to_probability, rng) for _ in range(a_count)]
        h1, a1, h1_drives, a1_drives = _simulate_first_half(
            home_ppd, away_ppd, home_to_probability, away_to_probability, rng
        )
        first_half_home_drives += h1_drives
        first_half_away_drives += a1_drives
        hs, as_ = sum(h_outcomes), sum(a_outcomes)
        home_first_scores.append(h1)
        away_first_scores.append(a1)
        first_home_sum += h1
        first_away_sum += a1
        if hs == as_:
            ot_home, ot_away, _ot_rounds = _simulate_overtime(
                home_ppd, away_ppd, home_to_probability, away_to_probability, rng
            )
            hs += ot_home
            as_ += ot_away
        home_scores.append(hs)
        away_scores.append(as_)
        margin = hs - as_
        total = hs + as_
        margin_sum += margin
        total_sum += total
        home_wins += margin > 0
        ties += margin == 0
        if lines.spread_home is not None:
            adjusted_margin = margin + lines.spread_home
            home_covers += adjusted_margin > 0
            home_cover_pushes += adjusted_margin == 0
        if lines.total is not None:
            overs += total > lines.total
            total_pushes += total == lines.total

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
        "projected_first_half_score": {
            home.name: round(first_home_sum / trials, 2),
            away.name: round(first_away_sum / trials, 2),
        },
        "projected_first_half_total": round((first_home_sum + first_away_sum) / trials, 2),
        "projected_first_half_drives": {
            home.name: round(first_half_home_drives / trials, 2),
            away.name: round(first_half_away_drives / trials, 2),
        },
        "first_half_engine": "30-minute clock-limited drive-duration approximation; not play-by-play",
        "score_ranges": {
            home.name: {"p10": _percentile(home_scores, 0.10), "median": _percentile(home_scores, 0.50), "p90": _percentile(home_scores, 0.90)},
            away.name: {"p10": _percentile(away_scores, 0.10), "median": _percentile(away_scores, 0.50), "p90": _percentile(away_scores, 0.90)},
        },
        "first_half_win_probability_home": round(sum(h > a for h, a in zip(home_first_scores, away_first_scores)) / trials, 4),
        "first_half_win_probability_away": round(sum(a > h for h, a in zip(home_first_scores, away_first_scores)) / trials, 4),
        "first_half_tie_probability": round(sum(h == a for h, a in zip(home_first_scores, away_first_scores)) / trials, 4),
        "home_win_probability": round(home_wins / trials, 4),
        "away_win_probability": round((trials - home_wins) / trials, 4),
        "expected_points_per_drive": {home.name: round(home_ppd, 3), away.name: round(away_ppd, 3)},
        "model_methodology": {
            "engine": "drive-level Monte Carlo with team-specific game efficiency and pace shocks",
            "sample_shrinkage": "team scoring efficiency shrunk toward 2.50 points/drive with weight games/(games+4)",
            "overtime": "college-style alternating possession approximation; conversion rounds after two rounds",
            "overtime_note": "not a rules-exact play-by-play overtime model",
            "calibration_status": "not empirically calibrated; evaluate against timestamped pregame ledger",
        },
        "simulation_precision": {
            "home_win_standard_error": round(math.sqrt((home_wins / trials) * (1 - home_wins / trials) / trials), 6),
            "home_win_95pct_margin": round(1.96 * math.sqrt((home_wins / trials) * (1 - home_wins / trials) / trials), 6),
            "home_efficiency_sample_weight": round(home_sample_weight, 4),
            "away_efficiency_sample_weight": round(away_sample_weight, 4),
        },
        "team_comparison": {home.name: _team_metrics(home), away.name: _team_metrics(away)},
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
        result["market"]["away_cover_probability"] = round((trials - home_covers - home_cover_pushes) / trials, 4)
        result["market"]["spread_push_probability"] = round(home_cover_pushes / trials, 4)
    if lines.total is not None:
        result["market"]["total_line"] = lines.total
        result["market"]["over_probability"] = round(overs / trials, 4)
        result["market"]["under_probability"] = round((trials - overs - total_pushes) / trials, 4)
        result["market"]["total_push_probability"] = round(total_pushes / trials, 4)
    return result


def _percentile(values: list[int], quantile: float) -> int:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return ordered[index]


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
        if team.source == "CollegeFootballData API" and team.as_of:
            try:
                from datetime import date
                age_days = (date.today() - date.fromisoformat(team.as_of)).days
                if age_days > 2:
                    warnings.append(
                        f"{team.name}: team statistics are {age_days} days old; "
                        "refresh was rate-limited and projections carry elevated data risk"
                    )
            except ValueError:
                warnings.append(f"{team.name}: team-statistics date could not be validated")
    return warnings


def _team_metrics(team: TeamProfile) -> dict:
    return {
        "offense": {
            "pass_yards_per_game": team.pass_yards_per_game,
            "pass_attempts_per_game": team.pass_attempts_per_game,
            "completions_per_game": team.completions_per_game,
            "completion_pct": team.completion_pct,
            "yards_per_pass_attempt": team.yards_per_pass_attempt,
            "pass_tds_per_game": team.pass_tds_per_game,
            "interceptions_per_game": team.interceptions_per_game,
            "pass_first_downs_per_game": team.pass_first_downs_per_game,
            "rush_yards_per_game": team.rush_yards_per_game,
            "rush_attempts_per_game": team.rush_attempts_per_game,
            "yards_per_carry": team.yards_per_carry,
            "rush_tds_per_game": team.rush_tds_per_game,
            "rush_first_downs_per_game": team.rush_first_downs_per_game,
            "total_yards_per_game": team.total_yards_per_game,
            "total_yards_per_play": team.yards_per_play,
            "plays_per_game": team.plays_per_game,
        },
        "defense": {
            "pass_yards_allowed_per_game": team.pass_yards_allowed_per_game,
            "plays_allowed_per_game": team.plays_allowed_per_game,
            "pass_first_downs_allowed_per_game": team.pass_first_downs_allowed_per_game,
            "rush_first_downs_allowed_per_game": team.rush_first_downs_allowed_per_game,
            "opponent_pass_attempts_per_game": team.opponent_pass_attempts_per_game,
            "opponent_completions_per_game": team.opponent_completions_per_game,
            "opponent_yards_per_completion": team.opponent_yards_per_completion,
            "opponent_yards_per_pass_attempt_allowed": team.opponent_yards_per_pass_attempt_allowed,
            "rush_yards_allowed_per_game": team.rush_yards_allowed_per_game,
            "opponent_rush_attempts_per_game": team.opponent_rush_attempts_per_game,
            "opponent_yards_per_carry_allowed": team.opponent_yards_per_carry_allowed,
            "total_yards_allowed_per_game": team.total_yards_allowed_per_game,
            "total_yards_per_play_allowed": team.yards_per_play_allowed,
        },
        "turnovers": {
            "giveaways_per_game": team.turnovers_per_game,
            "takeaways_per_game": team.takeaways_per_game,
            "turnover_margin_per_game": team.takeaways_per_game - team.turnovers_per_game,
        },
        "sample": {"games": team.games_sampled, "as_of": team.as_of, "source": team.source},
    }
