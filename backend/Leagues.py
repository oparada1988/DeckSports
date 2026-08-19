"""
DeckSports League Definitions
"""

from dataclasses import dataclass

@dataclass(frozen=True)
class LeagueConfig:
    key: str
    display_name: str
    sport_slug: str
    league_slug: str
    logo_url: str

LEAGUES: dict[str, LeagueConfig] = {
    "NFL": LeagueConfig(
        key="NFL",
        display_name="NFL (Football)",
        sport_slug="football",
        league_slug="nfl",
        logo_url="https://a.espncdn.com/i/teamlogos/leagues/500/nfl.png"
    ),
    "NBA": LeagueConfig(
        key="NBA",
        display_name="NBA (Basketball)",
        sport_slug="basketball",
        league_slug="nba",
        logo_url="https://a.espncdn.com/i/teamlogos/leagues/500/nba.png"
    ),
    "MLB": LeagueConfig(
        key="MLB",
        display_name="MLB (Baseball)",
        sport_slug="baseball",
        league_slug="mlb",
        logo_url="https://a.espncdn.com/i/teamlogos/leagues/500/mlb.png"
    ),
    "MLS": LeagueConfig(
        key="MLS",
        display_name="MLS (Soccer)",
        sport_slug="soccer",
        league_slug="usa.1",
        logo_url="https://a.espncdn.com/i/teamlogos/leagues/500/mls.png"
    ),
    "UFL": LeagueConfig(
        key="UFL",
        display_name="UFL (Football)",
        sport_slug="football",
        league_slug="ufl",
        logo_url="https://a.espncdn.com/i/teamlogos/leagues/500/ufl.png"
    ),
    "NHL": LeagueConfig(
        key="NHL",
        display_name="NHL (Hockey)",
        sport_slug="hockey",
        league_slug="nhl",
        logo_url="https://a.espncdn.com/i/teamlogos/leagues/500/nhl.png"
    ),
    "NCAA_FB": LeagueConfig(
        key="NCAA_FB",
        display_name="NCAA Football",
        sport_slug="football",
        league_slug="college-football",
        logo_url="https://a.espncdn.com/i/teamlogos/leagues/500/ncaa.png"
    ),
    "NCAA_MBB": LeagueConfig(
        key="NCAA_MBB",
        display_name="NCAA Men's Basketball",
        sport_slug="basketball",
        league_slug="mens-college-basketball",
        logo_url="https://a.espncdn.com/i/teamlogos/leagues/500/ncaa.png"
    ),
    "WNBA": LeagueConfig(
        key="WNBA",
        display_name="WNBA (Basketball)",
        sport_slug="basketball",
        league_slug="wnba",
        logo_url="https://a.espncdn.com/i/teamlogos/leagues/500/wnba.png"
    ),
}

LEAGUE_KEYS = list(LEAGUES.keys())
