"""
DeckSports Central Sports Data Service
Fetches ESPN scoreboard and team data, caches assets locally, and coordinates live state.
"""

import os
import io
import time
import hashlib
import threading
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Callable

import requests
from PIL import Image
import logging
log = logging.getLogger("DeckSports")
from gi.repository import GLib

from .Leagues import LEAGUES, LeagueConfig

def hex_to_rgba(hex_code: str | None, default: tuple[int, int, int, int] = (40, 40, 40, 255)) -> tuple[int, int, int, int]:
    if not hex_code:
        return default
    hex_clean = hex_code.lstrip("#").strip()
    if len(hex_clean) == 6:
        try:
            r = int(hex_clean[0:2], 16)
            g = int(hex_clean[2:4], 16)
            b = int(hex_clean[4:6], 16)
            return (r, g, b, 255)
        except ValueError:
            pass
    return default


@dataclass
class TeamInfo:
    id: str = ""
    name: str = "TBD"
    abbreviation: str = "TBD"
    short_name: str = "TBD"
    logo_url: str = ""
    score: str = "0"
    record: str = ""
    color: tuple[int, int, int, int] = (45, 45, 45, 255)
    alternate_color: tuple[int, int, int, int] = (220, 220, 220, 255)
    is_home: bool = False


@dataclass
class GameState:
    league_key: str = "NFL"
    followed_team_id: str = ""
    status_state: str = "off"   # "pre", "in", "post", "off"
    status_detail: str = "No Game Scheduled"
    clock: str = ""
    period: int = 0
    period_text: str = ""
    down_distance: str = ""
    possession_team_id: str | None = None
    possession_side: str | None = None  # "away", "home", or None
    away_team: TeamInfo = field(default_factory=TeamInfo)
    home_team: TeamInfo = field(default_factory=TeamInfo)
    next_game_date: str = ""
    next_game_time: str = ""
    next_game_opponent: str = ""
    last_updated: float = 0.0


class SportsService:
    def __init__(self):
        self.cache_dir = os.path.expanduser("~/.cache/DeckSports")
        self.logo_cache_dir = os.path.join(self.cache_dir, "logos")
        os.makedirs(self.logo_cache_dir, exist_ok=True)

        self.team_cache: dict[str, list[dict]] = {}
        self.image_cache: dict[str, Image.Image] = {}

        self.active_game_state = GameState()
        self.listeners: list[Callable[[GameState], None]] = []
        self._lock = threading.Lock()

        self._current_league: str = "NFL"
        self._current_team_id: str = ""
        self._refresh_seconds: int = 15
        self._timer_id: int | None = None
        self._is_fetching: bool = False
        self.hub_coords: tuple[int, int] | None = None

    def set_hub_coords(self, coords: tuple[int, int] | None):
        if coords and isinstance(coords, (list, tuple)) and len(coords) >= 2:
            self.hub_coords = (coords[0], coords[1])
        else:
            self.hub_coords = None
        self.notify_listeners()

    def add_listener(self, callback: Callable[[GameState], None]):
        with self._lock:
            if callback not in self.listeners:
                self.listeners.append(callback)

    def remove_listener(self, callback: Callable[[GameState], None]):
        with self._lock:
            if callback in self.listeners:
                self.listeners.remove(callback)

    def notify_listeners(self):
        with self._lock:
            callbacks = list(self.listeners)
        state_copy = self.active_game_state
        for cb in callbacks:
            try:
                cb(state_copy)
            except Exception as e:
                log.error(f"Error in SportsService listener callback: {e}")

    # --- Image & Logo Caching ---
    def get_image(self, url: str | None, max_size: tuple[int, int] = (80, 80)) -> Image.Image | None:
        if not url:
            return None

        cache_key = f"{url}_{max_size[0]}x{max_size[1]}"
        if cache_key in self.image_cache:
            return self.image_cache[cache_key]

        # Check local disk cache
        url_hash = hashlib.md5(url.encode()).hexdigest()
        file_path = os.path.join(self.logo_cache_dir, f"{url_hash}.png")

        try:
            if os.path.exists(file_path):
                img = Image.open(file_path).convert("RGBA")
            else:
                resp = requests.get(url, timeout=6)
                if resp.status_code == 200:
                    img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                    img.save(file_path, "PNG")
                else:
                    return None

            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            self.image_cache[cache_key] = img
            return img
        except Exception as e:
            log.trace(f"Failed to fetch or process logo from {url}: {e}")
            return None

    def get_league_logo(self, league_key: str, max_size: tuple[int, int] = (36, 36)) -> Image.Image | None:
        cfg = LEAGUES.get(league_key)
        if not cfg:
            return None
        return self.get_image(cfg.logo_url, max_size)

    # --- Teams Fetching ---
    def get_teams(self, league_key: str) -> list[dict]:
        """Return list of dicts: [{'id': ..., 'name': ..., 'abbreviation': ..., 'logo': ..., 'color': ...}]"""
        if league_key in self.team_cache and self.team_cache[league_key]:
            return self.team_cache[league_key]

        cfg = LEAGUES.get(league_key)
        if not cfg:
            return []

        url = f"https://site.api.espn.com/apis/site/v2/sports/{cfg.sport_slug}/{cfg.league_slug}/teams?limit=500"
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                team_list = []
                for sports_item in data.get("sports", []):
                    for league_item in sports_item.get("leagues", []):
                        for item in league_item.get("teams", []):
                            t = item.get("team", {})
                            team_id = str(t.get("id", ""))
                            logos = t.get("logos", [])
                            logo_href = logos[0].get("href", "") if logos else ""
                            team_list.append({
                                "id": team_id,
                                "name": t.get("displayName", "Unknown"),
                                "abbreviation": t.get("abbreviation", "TBD"),
                                "short_name": t.get("shortDisplayName", t.get("name", "TBD")),
                                "color": t.get("color", "333333"),
                                "alternate_color": t.get("alternateColor", "ffffff"),
                                "logo_url": logo_href,
                            })
                team_list.sort(key=lambda x: x["name"])
                self.team_cache[league_key] = team_list
                return team_list
        except Exception as e:
            log.error(f"Failed to fetch team list for {league_key}: {e}")

        return []

    # --- Live Game Data Fetching ---
    def update_config(self, league_key: str, team_id: str, refresh_seconds: int = 15):
        changed = (self._current_league != league_key) or (self._current_team_id != team_id) or (self._refresh_seconds != refresh_seconds)
        self._current_league = league_key
        self._current_team_id = team_id
        self._refresh_seconds = max(5, refresh_seconds)

        if changed:
            self.fetch_async()

    def fetch_async(self):
        if self._is_fetching:
            return
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        self._is_fetching = True
        try:
            self._fetch_and_parse()
        except Exception as e:
            log.error(f"Error fetching sports data: {e}")
        finally:
            self._is_fetching = False
            GLib.idle_add(self.notify_listeners)

    def _fetch_and_parse(self):
        cfg = LEAGUES.get(self._current_league)
        if not cfg:
            return

        scoreboard_url = f"https://site.api.espn.com/apis/site/v2/sports/{cfg.sport_slug}/{cfg.league_slug}/scoreboard"
        try:
            r = requests.get(scoreboard_url, timeout=8)
            if r.status_code != 200:
                log.warning(f"Scoreboard API returned {r.status_code}")
                return
            data = r.json()
        except Exception as e:
            log.warning(f"Failed to load scoreboard for {self._current_league}: {e}")
            return

        events = data.get("events", [])
        matched_event = None

        # Search for a game involving the followed team
        for ev in events:
            comp = ev.get("competitions", [{}])[0]
            for c in comp.get("competitors", []):
                t_id = str(c.get("id") or c.get("team", {}).get("id", ""))
                if t_id and t_id == str(self._current_team_id):
                    matched_event = ev
                    break
            if matched_event:
                break

        new_state = GameState(
            league_key=self._current_league,
            followed_team_id=self._current_team_id,
            last_updated=time.time()
        )

        if matched_event:
            self._parse_event_into_state(matched_event, new_state)
        else:
            # If team is not in today's scoreboard, query team schedule if available
            self._parse_off_game_state(new_state)

        with self._lock:
            self.active_game_state = new_state

    def _parse_event_into_state(self, ev: dict, state: GameState):
        comp = ev.get("competitions", [{}])[0]
        status_info = ev.get("status", {})
        status_type = status_info.get("type", {})

        raw_state = status_type.get("state", "off") # "pre", "in", "post"
        state.status_state = raw_state
        state.status_detail = status_type.get("shortDetail") or status_type.get("detail", "")
        state.clock = status_info.get("displayClock", "")
        state.period = status_info.get("period", 0)

        # Period text formatting (e.g. Q1, Bot 3rd, Half)
        state.period_text = status_type.get("shortDetail", "")

        # Competitors (Away & Home)
        for c in comp.get("competitors", []):
            home_away = c.get("homeAway", "away")
            t_data = c.get("team", {})
            logos = t_data.get("logos", [])
            logo_href = logos[0].get("href", "") if logos else t_data.get("logo", "")

            records = c.get("records", [])
            record_str = records[0].get("summary", "") if records else ""

            team_obj = TeamInfo(
                id=str(c.get("id") or t_data.get("id", "")),
                name=t_data.get("displayName", "TBD"),
                abbreviation=t_data.get("abbreviation", "TBD"),
                short_name=t_data.get("shortDisplayName", t_data.get("name", "TBD")),
                logo_url=logo_href,
                score=str(c.get("score", "0")),
                record=record_str,
                color=hex_to_rgba(t_data.get("color")),
                alternate_color=hex_to_rgba(t_data.get("alternateColor"), (255, 255, 255, 255)),
                is_home=(home_away == "home")
            )

            if home_away == "home":
                state.home_team = team_obj
            else:
                state.away_team = team_obj

        # Situation (Possession, Down & Distance, Outs/Bases)
        situation = comp.get("situation", {})
        if situation:
            state.down_distance = situation.get("downDistanceText", "")
            poss_id = str(situation.get("possession", ""))
            state.possession_team_id = poss_id if poss_id else None

            # Baseball: determine active batting team by half inning
            if state.league_key == "MLB":
                if "Top" in state.status_detail:
                    state.possession_side = "away"
                elif "Bot" in state.status_detail:
                    state.possession_side = "home"
            elif poss_id:
                if poss_id == state.away_team.id:
                    state.possession_side = "away"
                elif poss_id == state.home_team.id:
                    state.possession_side = "home"

        # Pre-game date formatting
        if raw_state == "pre":
            self._format_game_datetime(ev.get("date", ""), state)

    def _parse_off_game_state(self, state: GameState):
        cfg = LEAGUES.get(self._current_league)
        if not cfg or not self._current_team_id:
            state.status_state = "off"
            state.status_detail = "No Game"
            return

        # Fetch team schedule to find next game
        url = f"https://site.api.espn.com/apis/site/v2/sports/{cfg.sport_slug}/{cfg.league_slug}/teams/{self._current_team_id}/schedule"
        try:
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                events = r.json().get("events", [])
                now = datetime.now(timezone.utc)
                for ev in events:
                    ev_date_str = ev.get("date", "")
                    try:
                        ev_dt = datetime.fromisoformat(ev_date_str.replace("Z", "+00:00"))
                        if ev_dt > now:
                            self._parse_event_into_state(ev, state)
                            state.status_state = "pre"
                            return
                    except Exception:
                        pass
        except Exception as e:
            log.trace(f"Schedule lookup error: {e}")

        # Fallback if no upcoming game found
        teams = self.get_teams(self._current_league)
        my_team = next((t for t in teams if str(t["id"]) == str(self._current_team_id)), None)
        if my_team:
            state.away_team = TeamInfo(
                id=my_team["id"],
                name=my_team["name"],
                abbreviation=my_team["abbreviation"],
                logo_url=my_team["logo_url"],
                color=hex_to_rgba(my_team["color"]),
                alternate_color=hex_to_rgba(my_team["alternate_color"])
            )
        state.status_state = "off"
        state.status_detail = "Off Season / Bye"

    def _format_game_datetime(self, iso_date: str, state: GameState):
        if not iso_date:
            return
        try:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00")).astimezone()
            state.next_game_date = dt.strftime("%a, %b %d")
            state.next_game_time = dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            state.next_game_date = iso_date[:10]
            state.next_game_time = ""
