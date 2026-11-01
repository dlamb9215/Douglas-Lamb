
"""
DOUG'S ELITE GAME SIMULATOR
NFL TEAM DATABASE
"""

NFL_TEAMS = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SF": "San Francisco 49ers",
    "SEA": "Seattle Seahawks",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders"
}


def create_team_database():
    database = {}

    for abbreviation, name in NFL_TEAMS.items():
        database[abbreviation] = {
            "name": name,
            "offense": {
                "passing": {},
                "rushing": {},
                "total": {}
            },
            "defense": {
                "passing": {},
                "rushing": {},
                "total": {}
            },
            "turnovers": {
                "takeaways": None,
                "giveaways": None,
                "differential": None
            }
        }

    return database


def get_team(abbreviation):
    database = create_team_database()

    if abbreviation not in database:
        raise ValueError("Invalid NFL team abbreviation")

    return database[abbreviation]


if __name__ == "__main__":
    teams = create_team_database()

    print("DOUG'S ELITE GAME SIMULATOR")
    print("NFL TEAM DATABASE")
    print("==========================")
    print("Total teams:", len(teams))
    print("Database initialized successfully.")
