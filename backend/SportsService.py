"""
DeckSports Central Sports Data Service
Multi-instance ESPN scoreboard coordinator with shared league caching and smart hub pairing.
"""

import os
import io
import time
import json
import hashlib
import threading
import math
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

        # Multi-game state dictionary keyed by (league_key, team_id)
        self.game_states: dict[tuple[str, str], GameState] = {}

        # Shared league scoreboard cache: {league_key: {"time": float, "data": dict}}
        self.league_scoreboard_cache: dict[str, dict] = {}
        self._league_fetch_locks: dict[str, bool] = {}

        self.listeners: list[Callable[[str, str, GameState], None]] = []
        self._lock = threading.Lock()

        # Hub spatial registry: action_id -> {"coords": (x, y), "league": str, "team_id": str}
        self.hubs: dict[int, dict] = {}
        self.active_score_actions: set[int] = set()

    # --- Hub & Satellite Registry ---
    def register_hub(self, action_id: int, coords: tuple[int, int] | None, league_key: str, team_id: str, display_mode: int = 0):
        with self._lock:
            self.hubs[action_id] = {
                "coords": (coords[0], coords[1]) if (coords and isinstance(coords, (list, tuple)) and len(coords) >= 2) else None,
                "league": league_key,
                "team_id": team_id,
                "display_mode": display_mode
            }
        self.notify_listeners(league_key, team_id)

    def unregister_hub(self, action_id: int):
        with self._lock:
            info = self.hubs.pop(action_id, None)
        if info:
            self.notify_listeners(info["league"], info["team_id"])

    def register_score_action(self, action_id: int):
        with self._lock:
            self.active_score_actions.add(action_id)
        # Notify all hubs so they adapt to 3-button mode
        self.notify_all()

    def unregister_score_action(self, action_id: int):
        with self._lock:
            self.active_score_actions.discard(action_id)
        self.notify_all()

    def has_score_actions(self) -> bool:
        with self._lock:
            return len(self.active_score_actions) > 0

    def get_nearest_hub_target(self, my_coords: tuple[int, int] | None) -> tuple[str, str, str]:
        """
        Given coordinates (my_x, my_y), finds the best matching GameHub on the deck.
        Returns (league_key, team_id, side_str) where side_str is 'away', 'home', 'followed', or 'opponent'.
        """
        with self._lock:
            hubs_list = list(self.hubs.values())

        if not hubs_list:
            return ("NFL", "", "away")

        if not my_coords or not isinstance(my_coords, (list, tuple)) or len(my_coords) < 2:
            first = hubs_list[0]
            return (first["league"], first["team_id"], "away")

        my_x, my_y = my_coords[0], my_coords[1]

        # 1. Prefer hubs on the exact same row (my_y == hub_y)
        same_row_hubs = [h for h in hubs_list if h["coords"] and h["coords"][1] == my_y]

        candidates = same_row_hubs if same_row_hubs else [h for h in hubs_list if h["coords"]]
        if not candidates:
            first = hubs_list[0]
            return (first["league"], first["team_id"], "away")

        # Find closest candidate horizontally/Euclidean
        best_hub = None
        min_dist = float("inf")
        for h in candidates:
            hx, hy = h["coords"][0], h["coords"][1]
            dist = math.hypot(my_x - hx, (my_y - hy) * 2) # weight vertical distance higher
            if dist < min_dist:
                min_dist = dist
                best_hub = h

        if not best_hub:
            best_hub = hubs_list[0]

        hub_x = best_hub["coords"][0] if best_hub["coords"] else 0
        display_mode = best_hub.get("display_mode", 0)

        if display_mode == 1:
            # Always My Team on Left
            side = "followed" if my_x < hub_x else "opponent"
        else:
            # Broadcast mode: Away Left, Home Right
            side = "home" if my_x > hub_x else "away"

        return (best_hub["league"], best_hub["team_id"], side)

    # --- Listener Management ---
    def add_listener(self, callback: Callable[[str, str, GameState], None]):
        with self._lock:
            if callback not in self.listeners:
                self.listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, str, GameState], None]):
        with self._lock:
            if callback in self.listeners:
                self.listeners.remove(callback)

    def notify_listeners(self, league_key: str, team_id: str):
        state = self.get_game_state(league_key, team_id)
        with self._lock:
            callbacks = list(self.listeners)
        for cb in callbacks:
            try:
                cb(league_key, team_id, state)
            except Exception as e:
                log.error(f"Error in SportsService listener callback: {e}")

    def notify_all(self):
        with self._lock:
            items = list(self.game_states.items())
            callbacks = list(self.listeners)
        for (l, t), st in items:
            for cb in callbacks:
                try:
                    cb(l, t, st)
                except Exception:
                    pass

    def get_game_state(self, league_key: str, team_id: str) -> GameState:
        with self._lock:
            key = (league_key, str(team_id))
            if key in self.game_states:
                return self.game_states[key]
            # Return fresh default state
            new_st = GameState(league_key=league_key, followed_team_id=str(team_id))
            self.game_states[key] = new_st
            return new_st

    # --- Non-Blocking Image & Logo Caching ---
    def get_image(self, url: str | None, max_size: tuple[int, int] = (80, 80)) -> Image.Image | None:
        if not url:
            return None

        cache_key = f"{url}_{max_size[0]}x{max_size[1]}"
        if cache_key in self.image_cache:
            return self.image_cache[cache_key]

        # Check local disk cache
        url_hash = hashlib.md5(url.encode()).hexdigest()
        file_path = os.path.join(self.logo_cache_dir, f"{url_hash}.png")

        if os.path.exists(file_path):
            try:
                img = Image.open(file_path).convert("RGBA")
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                self.image_cache[cache_key] = img
                return img
            except Exception:
                pass

        # If not cached on disk, fetch asynchronously without blocking the UI thread
        def _fetch_img_bg():
            try:
                resp = requests.get(url, timeout=6)
                if resp.status_code == 200:
                    img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                    img.save(file_path, "PNG")
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    self.image_cache[cache_key] = img
                    GLib.idle_add(self.notify_all)
            except Exception:
                pass

        threading.Thread(target=_fetch_img_bg, daemon=True).start()
        return None

    def get_league_logo(self, league_key: str, max_size: tuple[int, int] = (36, 36)) -> Image.Image | None:
        cfg = LEAGUES.get(league_key)
        if not cfg:
            return None
        return self.get_image(cfg.logo_url, max_size)

    # --- Teams Fetching with Disk Caching ---
    def get_teams(self, league_key: str) -> list[dict]:
        if league_key in self.team_cache and self.team_cache[league_key]:
            return self.team_cache[league_key]

        disk_teams_file = os.path.join(self.cache_dir, f"teams_{league_key}.json")
        if os.path.exists(disk_teams_file):
            try:
                with open(disk_teams_file, "r") as f:
                    cached_data = json.load(f)
                    if cached_data and isinstance(cached_data, list):
                        self.team_cache[league_key] = cached_data
                        return cached_data
            except Exception:
                pass

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

                try:
                    with open(disk_teams_file, "w") as f:
                        json.dump(team_list, f)
                except Exception:
                    pass

                return team_list
        except Exception as e:
            log.error(f"Failed to fetch team list for {league_key}: {e}")

        return []

    # --- Shared League Fetching & Multi-Game Parsing ---
    def fetch_async(self, league_key: str, team_id: str, force: bool = False, refresh_seconds: int = 15):
        if not league_key or not team_id:
            return

        now = time.time()
        cached = self.league_scoreboard_cache.get(league_key)

        # If we already have fresh scoreboard data for this league, parse directly
        if not force and cached and (now - cached["time"] < refresh_seconds):
            self._update_team_from_data(league_key, team_id, cached["data"])
            return

        if self._league_fetch_locks.get(league_key, False):
            return

        self._league_fetch_locks[league_key] = True
        threading.Thread(target=self._fetch_league_worker, args=(league_key, team_id), daemon=True).start()

    def _fetch_league_worker(self, league_key: str, team_id: str):
        try:
            cfg = LEAGUES.get(league_key)
            if not cfg:
                return

            scoreboard_url = f"https://site.api.espn.com/apis/site/v2/sports/{cfg.sport_slug}/{cfg.league_slug}/scoreboard"
            r = requests.get(scoreboard_url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                self.league_scoreboard_cache[league_key] = {
                    "time": time.time(),
                    "data": data
                }

                # Update all tracked teams for this league
                with self._lock:
                    target_teams = [t for (l, t) in self.game_states.keys() if l == league_key]
                if str(team_id) not in target_teams:
                    target_teams.append(str(team_id))

                for t_id in target_teams:
                    self._update_team_from_data(league_key, t_id, data)
        except Exception as e:
            log.error(f"Error fetching sports scoreboard for {league_key}: {e}")
        finally:
            self._league_fetch_locks[league_key] = False

    def _extract_logo_url(self, t_data: dict) -> str:
        logos = t_data.get("logos")
        if logos and isinstance(logos, list) and len(logos) > 0:
            first = logos[0]
            if isinstance(first, dict):
                return first.get("href", "")
            elif isinstance(first, str):
                return first
        logo = t_data.get("logo")
        if isinstance(logo, str):
            return logo
        elif isinstance(logo, list) and len(logo) > 0:
            first = logo[0]
            if isinstance(first, dict):
                return first.get("href", "")
            elif isinstance(first, str):
                return first
        return ""

    def _update_team_from_data(self, league_key: str, team_id: str, data: dict):
        events = data.get("events", [])
        matched_event = None

        for ev in events:
            comp = ev.get("competitions", [{}])[0]
            for c in comp.get("competitors", []):
                t_id = str(c.get("id") or c.get("team", {}).get("id", ""))
                if t_id and t_id == str(team_id):
                    matched_event = ev
                    break
            if matched_event:
                break

        is_stale_final = False
        if matched_event:
            status_info = matched_event.get("status", {})
            status_type = status_info.get("type", {})
            raw_state = status_type.get("state", "off")
            if raw_state == "post":
                # Check if game completed > 24 hours ago
                ev_date_str = matched_event.get("date", "")
                if ev_date_str:
                    try:
                        ev_dt = datetime.fromisoformat(ev_date_str.replace("Z", "+00:00"))
                        now_utc = datetime.now(timezone.utc)
                        # If more than 24 hours have elapsed since game time
                        if (now_utc - ev_dt).total_seconds() > 24 * 3600:
                            is_stale_final = True
                    except Exception:
                        pass

        new_state = GameState(
            league_key=league_key,
            followed_team_id=str(team_id),
            last_updated=time.time()
        )

        if matched_event and not is_stale_final:
            self._parse_event_into_state(matched_event, new_state)
        else:
            self._parse_off_game_state(new_state)

        with self._lock:
            self.game_states[(league_key, str(team_id))] = new_state

        # Pre-cache logos
        if new_state.away_team.logo_url:
            self.get_image(new_state.away_team.logo_url)
        if new_state.home_team.logo_url:
            self.get_image(new_state.home_team.logo_url)

        GLib.idle_add(lambda: self.notify_listeners(league_key, str(team_id)))

    def _parse_event_into_state(self, ev: dict, state: GameState):
        comp = ev.get("competitions", [{}])[0]
        status_info = ev.get("status", {})
        status_type = status_info.get("type", {})

        raw_state = status_type.get("state", "off")
        state.status_state = raw_state
        state.status_detail = status_type.get("shortDetail") or status_type.get("detail", "")
        state.clock = status_info.get("displayClock", "")
        state.period = status_info.get("period", 0)
        state.period_text = status_type.get("shortDetail", "")

        all_teams = self.get_teams(state.league_key)
        team_dict = {str(t["id"]): t for t in all_teams}

        for c in comp.get("competitors", []):
            home_away = c.get("homeAway", "away")
            t_data = c.get("team", {})
            t_id = str(c.get("id") or t_data.get("id", ""))
            cached_team = team_dict.get(t_id, {})

            logo_href = self._extract_logo_url(t_data) or cached_team.get("logo_url", "")
            records = c.get("records", [])
            record_str = records[0].get("summary", "") if records else cached_team.get("record", "")

            color_hex = t_data.get("color") or cached_team.get("color")
            alt_hex = t_data.get("alternateColor") or cached_team.get("alternate_color")

            name = t_data.get("displayName") or cached_team.get("name", "TBD")
            abbreviation = t_data.get("abbreviation") or cached_team.get("abbreviation", "TBD")
            short_name = t_data.get("shortDisplayName") or t_data.get("name") or cached_team.get("short_name", "TBD")

            team_obj = TeamInfo(
                id=t_id,
                name=name,
                abbreviation=abbreviation,
                short_name=short_name,
                logo_url=logo_href,
                score=str(c.get("score", "")) if raw_state in ("in", "post") else "",
                record=record_str,
                color=hex_to_rgba(color_hex),
                alternate_color=hex_to_rgba(alt_hex, (255, 255, 255, 255)),
                is_home=(home_away == "home")
            )

            if home_away == "home":
                state.home_team = team_obj
            else:
                state.away_team = team_obj

        situation = comp.get("situation", {})
        if situation:
            state.down_distance = situation.get("downDistanceText", "")
            poss_id = str(situation.get("possession", ""))
            state.possession_team_id = poss_id if poss_id else None

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

        if raw_state == "pre" or ev.get("date"):
            self._format_game_datetime(ev.get("date", ""), state)

    def _parse_off_game_state(self, state: GameState):
        cfg = LEAGUES.get(state.league_key)
        if not cfg or not state.followed_team_id:
            state.status_state = "off"
            state.status_detail = "No Game"
            return

        url = f"https://site.api.espn.com/apis/site/v2/sports/{cfg.sport_slug}/{cfg.league_slug}/teams/{state.followed_team_id}/schedule"
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
                            self._format_game_datetime(ev_date_str, state)
                            state.away_team.score = ""
                            state.home_team.score = ""
                            return
                    except Exception:
                        pass
        except Exception as e:
            log.error(f"Schedule lookup error: {e}")

        teams = self.get_teams(state.league_key)
        my_team = next((t for t in teams if str(t["id"]) == str(state.followed_team_id)), None)
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
            now = datetime.now(dt.tzinfo)
            if dt.date() == now.date():
                state.next_game_date = "TODAY"
            elif (dt.date() - now.date()).days == 1:
                state.next_game_date = "TOMORROW"
            else:
                state.next_game_date = dt.strftime("%a, %b %d")
            state.next_game_time = dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            state.next_game_date = iso_date[:10]
            state.next_game_time = ""
