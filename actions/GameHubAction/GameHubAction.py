"""
DeckSports GameHubAction
Middle master action for team configuration, game schedule, clock, and possession indicator.
"""

import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from PIL import Image, ImageDraw, ImageFont

from src.backend.PluginManager.ActionBase import ActionBase
from ...backend.Leagues import LEAGUES, LEAGUE_KEYS
from ...backend.SportsService import GameState

REFRESH_OPTIONS = [
    ("Adaptive (15s live / 10m off)", 15),
    ("10 Seconds (Fast)", 10),
    ("15 Seconds (Standard)", 15),
    ("30 Seconds", 30),
    ("60 Seconds", 60),
]

DISPLAY_MODES = [
    "Broadcast (Away Left / Home Right)",
    "Always My Team on Left"
]

def get_bundled_font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    plugin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    bundled_font = os.path.join(plugin_dir, "assets", "fonts", "ScoreFont-Bold.ttf")
    if os.path.exists(bundled_font):
        try:
            return ImageFont.truetype(bundled_font, size)
        except Exception:
            pass

    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    ]
    for p in font_candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

class GameHubAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._league_row: Adw.ComboRow | None = None
        self._team_row: Adw.ComboRow | None = None
        self._refresh_row: Adw.ComboRow | None = None
        self._display_mode_row: Adw.ComboRow | None = None

        self._team_model: Gtk.StringList | None = None
        self._current_team_list: list[dict] = []
        self._is_updating_ui: bool = False

    def on_ready(self):
        self.plugin_base.sports_service.add_listener(self.on_game_state_updated)
        coords = getattr(self.input_ident, "coords", None)
        self.plugin_base.sports_service.set_hub_coords(coords)
        self._sync_config_to_service()
        self.update_display()

    def on_game_state_updated(self, state: GameState):
        GLib.idle_add(self.update_display)

    def on_tick(self):
        # Trigger background fetch check
        self.plugin_base.sports_service.fetch_async()

    def on_key_down(self):
        # Instant manual refresh on press
        self.plugin_base.sports_service.fetch_async()

    # --- Sidebar Configuration UI ---
    def get_config_rows(self) -> list:
        rows = []

        # 1. League Selector
        league_model = Gtk.StringList()
        for k in LEAGUE_KEYS:
            league_model.append(LEAGUES[k].display_name)

        self._league_row = Adw.ComboRow(
            title="Sports League",
            subtitle="Select the league to track",
            model=league_model
        )

        settings = self.get_settings()
        saved_league = settings.get("league", "NFL")
        if saved_league in LEAGUE_KEYS:
            self._league_row.set_selected(LEAGUE_KEYS.index(saved_league))

        self._league_row.connect("notify::selected", self._on_league_changed)
        rows.append(self._league_row)

        # 2. Main / Followed Team Selector
        self._team_model = Gtk.StringList()
        self._team_row = Adw.ComboRow(
            title="Main / Home Team",
            subtitle="Your followed team for this widget",
            model=self._team_model
        )

        self._populate_team_dropdown(saved_league, initial_select=settings.get("team_id", ""))
        self._team_row.connect("notify::selected", self._on_team_changed)
        rows.append(self._team_row)

        # 3. Refresh Rate Selector
        refresh_model = Gtk.StringList()
        for label, _ in REFRESH_OPTIONS:
            refresh_model.append(label)

        self._refresh_row = Adw.ComboRow(
            title="Live Refresh Rate",
            subtitle="Adaptive mode recommended for live games",
            model=refresh_model
        )
        saved_refresh = settings.get("refresh_seconds", 15)
        refresh_idx = next((i for i, (_, s) in enumerate(REFRESH_OPTIONS) if s == saved_refresh), 0)
        self._refresh_row.set_selected(refresh_idx)
        self._refresh_row.connect("notify::selected", self._on_refresh_changed)
        rows.append(self._refresh_row)

        # 4. Display Mode (Home/Away layout)
        display_model = Gtk.StringList()
        for mode in DISPLAY_MODES:
            display_model.append(mode)

        self._display_mode_row = Adw.ComboRow(
            title="Scoreboard Alignment",
            subtitle="How teams are placed on Left and Right buttons",
            model=display_model
        )
        saved_mode = settings.get("display_mode", 0)
        self._display_mode_row.set_selected(min(saved_mode, len(DISPLAY_MODES) - 1))
        self._display_mode_row.connect("notify::selected", self._on_display_mode_changed)
        rows.append(self._display_mode_row)

        return rows

    def _populate_team_dropdown(self, league_key: str, initial_select: str = ""):
        self._is_updating_ui = True
        self._current_team_list = self.plugin_base.sports_service.get_teams(league_key)

        # Clear existing items
        while self._team_model.get_n_items() > 0:
            self._team_model.remove(0)

        selected_index = 0
        for i, t in enumerate(self._current_team_list):
            self._team_model.append(t["name"])
            if initial_select and str(t["id"]) == str(initial_select):
                selected_index = i

        if self._current_team_list:
            self._team_row.set_selected(selected_index)
        self._is_updating_ui = False

    def _on_league_changed(self, row, _pspec):
        if self._is_updating_ui:
            return
        idx = row.get_selected()
        if 0 <= idx < len(LEAGUE_KEYS):
            new_league = LEAGUE_KEYS[idx]
            settings = self.get_settings()
            settings["league"] = new_league
            self.set_settings(settings)

            # Reload teams for this league
            self._populate_team_dropdown(new_league)
            if self._current_team_list:
                first_team_id = self._current_team_list[0]["id"]
                settings["team_id"] = first_team_id
                self.set_settings(settings)

            self._sync_config_to_service()

    def _on_team_changed(self, row, _pspec):
        if self._is_updating_ui:
            return
        idx = row.get_selected()
        if 0 <= idx < len(self._current_team_list):
            team_obj = self._current_team_list[idx]
            settings = self.get_settings()
            settings["team_id"] = team_obj["id"]
            self.set_settings(settings)

            self._sync_config_to_service()

    def _on_refresh_changed(self, row, _pspec):
        idx = row.get_selected()
        if 0 <= idx < len(REFRESH_OPTIONS):
            _, seconds = REFRESH_OPTIONS[idx]
            settings = self.get_settings()
            settings["refresh_seconds"] = seconds
            self.set_settings(settings)
            self._sync_config_to_service()

    def _on_display_mode_changed(self, row, _pspec):
        idx = row.get_selected()
        settings = self.get_settings()
        settings["display_mode"] = idx
        self.set_settings(settings)
        # Notify sports service listeners to re-orient sides
        self.plugin_base.sports_service.notify_listeners()

    def _sync_config_to_service(self):
        settings = self.get_settings()
        league = settings.get("league", "NFL")
        team_id = settings.get("team_id", "")
        refresh = settings.get("refresh_seconds", 15)

        if not team_id:
            teams = self.plugin_base.sports_service.get_teams(league)
            if teams:
                team_id = teams[0]["id"]
                settings["team_id"] = team_id
                self.set_settings(settings)

        self.plugin_base.sports_service.update_config(league, team_id, refresh)

    # --- Canvas Rendering with Pillow ---
    def update_display(self):
        coords = getattr(self.input_ident, "coords", None)
        self.plugin_base.sports_service.set_hub_coords(coords)

        state = self.plugin_base.sports_service.active_game_state

        img = Image.new("RGBA", (100, 100), (20, 22, 28, 255))
        draw = ImageDraw.Draw(img)

        # Header background banner
        draw.rectangle([(0, 0), (100, 28)], fill=(32, 35, 45, 255))
        draw.line([(0, 28), (100, 28)], fill=(55, 60, 75, 255), width=1)

        # 1. League Logo (Centered in header)
        league_logo = self.plugin_base.sports_service.get_league_logo(state.league_key, max_size=(24, 24))
        if league_logo:
            lx = (100 - league_logo.width) // 2
            ly = (28 - league_logo.height) // 2
            img.alpha_composite(league_logo, (lx, ly))
        else:
            font_hdr = get_bundled_font(12)
            draw.text((50, 14), state.league_key, fill=(200, 205, 215, 255), anchor="mm", font=font_hdr)

        # 2. Body State Rendering
        if state.status_state == "in":
            # LIVE GAME STATE
            clock_text = state.clock if state.clock else state.period_text
            period_str = f"Q{state.period}" if state.period and state.league_key in ("NFL", "NBA", "UFL") else state.period_text

            font_period = get_bundled_font(13)
            font_clock = get_bundled_font(15)
            draw.text((50, 43), period_str, fill=(255, 210, 50, 255), anchor="mm", font=font_period)
            draw.text((50, 60), clock_text, fill=(255, 255, 255, 255), anchor="mm", font=font_clock)

            # Possession Arrow at Bottom
            font_poss = get_bundled_font(11)
            if state.possession_side == "away":
                draw.rectangle([(8, 76), (92, 94)], fill=(180, 40, 40, 255))
                draw.text((50, 85), "◀ BALL", fill=(255, 255, 255, 255), anchor="mm", font=font_poss)
            elif state.possession_side == "home":
                draw.rectangle([(8, 76), (92, 94)], fill=(40, 120, 180, 255))
                draw.text((50, 85), "BALL ▶", fill=(255, 255, 255, 255), anchor="mm", font=font_poss)
            elif state.down_distance:
                draw.text((50, 85), state.down_distance[:12], fill=(180, 185, 195, 255), anchor="mm", font=font_poss)
            else:
                draw.text((50, 85), "LIVE", fill=(100, 255, 120, 255), anchor="mm", font=font_poss)

        elif state.status_state == "pre":
            # UPCOMING GAME STATE
            font_sub = get_bundled_font(11)
            font_main = get_bundled_font(13)
            draw.text((50, 42), "NEXT GAME", fill=(140, 150, 170, 255), anchor="mm", font=font_sub)
            draw.text((50, 60), state.next_game_date, fill=(255, 255, 255, 255), anchor="mm", font=font_main)
            draw.text((50, 79), state.next_game_time, fill=(255, 210, 60, 255), anchor="mm", font=font_sub)

        elif state.status_state == "post":
            # FINAL / POST GAME
            font_status = get_bundled_font(13)
            font_score = get_bundled_font(15)
            font_det = get_bundled_font(11)

            draw.text((50, 41), "FINAL", fill=(255, 75, 75, 255), anchor="mm", font=font_status)

            # Mini team logos flanking the score if available
            away_logo = self.plugin_base.sports_service.get_image(state.away_team.logo_url, max_size=(18, 18))
            if away_logo:
                img.alpha_composite(away_logo, (10, 51))

            home_logo = self.plugin_base.sports_service.get_image(state.home_team.logo_url, max_size=(18, 18))
            if home_logo:
                img.alpha_composite(home_logo, (72, 51))

            summary = f"{state.away_team.score} - {state.home_team.score}"
            draw.text((50, 60), summary, fill=(255, 255, 255, 255), anchor="mm", font=font_score)
            draw.text((50, 81), state.status_detail[:14], fill=(170, 175, 185, 255), anchor="mm", font=font_det)

        else:
            # OFF-SEASON / NO GAME
            font_lbl = get_bundled_font(12)
            draw.text((50, 52), "SCHEDULE", fill=(140, 150, 170, 255), anchor="mm", font=font_lbl)
            draw.text((50, 72), "STANDBY", fill=(200, 205, 215, 255), anchor="mm", font=font_lbl)

        # Outer border
        draw.rectangle([(0, 0), (99, 99)], outline=(60, 65, 80, 255), width=1)

        self.set_media(image=img)
