import os
import webbrowser
import threading
import globals as gl
from functools import lru_cache
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from PIL import Image, ImageDraw, ImageFont

from src.backend.PluginManager.ActionBase import ActionBase
from src.backend.DeckManagement.InputIdentifier import Input
try:
    from ...backend.Leagues import LEAGUES, LEAGUE_KEYS
    from ...backend.SportsService import GameState
except (ImportError, ValueError):
    from backend.Leagues import LEAGUES, LEAGUE_KEYS
    from backend.SportsService import GameState

REFRESH_OPTIONS = [
    ("Adaptive (5s Live / 60s Final)", 5),
    ("5 Seconds (Ultra-Fast Live)", 5),
    ("10 Seconds (Fast)", 10),
    ("15 Seconds (Standard)", 15),
    ("30 Seconds (Eco)", 30),
    ("60 Seconds (Passive)", 60),
]

DISPLAY_MODES = [
    "Broadcast (Away Left / Home Right)",
    "Always My Team on Left"
]

HOLD_DESTINATIONS = [
    ("ESPN Gamecast / Match Center (Default)", "espn"),
    ("Official League Match Center", "league"),
    ("Custom Web URL", "custom")
]

LEAGUE_URLS = {
    "NFL": "https://www.nfl.com/scores",
    "NBA": "https://www.nba.com/games",
    "MLB": "https://www.mlb.com/scores",
    "NHL": "https://www.nhl.com/scores",
    "MLS": "https://www.mlssoccer.com/schedule/matches",
    "UFL": "https://www.theufl.com/schedule",
    "WNBA": "https://www.wnba.com/scores",
    "NCAA_FB": "https://www.ncaa.com/scoreboard/football/fbs",
    "NCAA_BK": "https://www.ncaa.com/scoreboard/basketball-men/d1"
}

@lru_cache(maxsize=32)
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
        self._clock_timer_id: int | None = None

    def _ensure_media_control(self):
        try:
            if not self.get_is_present():
                return
            own_idx = self.get_own_action_index()
            if own_idx is None or own_idx < 0:
                return
            input_state = self.get_state()
            if input_state and hasattr(input_state, "action_permission_manager"):
                pm = input_state.action_permission_manager
                curr_idx = pm.get_image_control_index()
                if curr_idx is None or curr_idx != own_idx:
                    state_dict = pm.get_state_dict()
                    actions = state_dict.get("actions", [])
                    if curr_idx is None or len(actions) <= 1:
                        pm.set_image_control_index(own_idx, reload_pages=False, reload_self=False)
        except Exception:
            pass

    def _manage_clock_timer(self, is_live: bool):
        if is_live and self._clock_timer_id is None:
            self._clock_timer_id = GLib.timeout_add(1000, self._on_clock_tick)
        elif not is_live and self._clock_timer_id is not None:
            try:
                GLib.source_remove(self._clock_timer_id)
            except Exception:
                pass
            self._clock_timer_id = None

    def _on_clock_tick(self) -> bool:
        if not self.get_is_present():
            self._clock_timer_id = None
            return False
        self.update_display()
        return True

    def on_ready(self):
        self._ensure_media_control()

        if hasattr(self.plugin_base, "_auto_provision_pages"):
            self.plugin_base._auto_provision_pages()

        settings = self.get_settings()
        league = settings.get("league", "NFL")
        team_id = settings.get("team_id", "")
        refresh = settings.get("refresh_seconds", 15)

        dash_target = self.plugin_base.sports_service.get_active_dashboard_target()
        page_path = getattr(self.page, "json_path", "") if getattr(self, "page", None) else ""
        is_hub_page = "GameHub" in os.path.basename(str(page_path))

        if dash_target and (is_hub_page or not settings.get("league")):
            league, team_id = dash_target
            settings["league"] = league
            settings["team_id"] = team_id
            self.set_settings(settings)
        elif not team_id:
            teams = self.plugin_base.sports_service.get_teams(league)
            if teams:
                team_id = str(teams[0]["id"])
                settings["team_id"] = team_id
                self.set_settings(settings)

        coords = getattr(self.input_ident, "coords", None)
        display_mode = settings.get("display_mode", 0)
        self.plugin_base.sports_service.register_hub(id(self), coords, league, team_id, display_mode, action_obj=self)
        self.plugin_base.sports_service.add_listener(self.on_game_state_updated)

        self.plugin_base.sports_service.fetch_async(league, team_id, force=True, refresh_seconds=refresh)
        self.plugin_base.sports_service.fetch_game_summary(league, team_id, force=True)
        GLib.idle_add(self.update_display)

    def on_remove(self):
        if self._clock_timer_id is not None:
            try:
                GLib.source_remove(self._clock_timer_id)
            except Exception:
                pass
            self._clock_timer_id = None
        self.plugin_base.sports_service.unregister_hub(id(self))
        self.plugin_base.sports_service.remove_listener(self.on_game_state_updated)

    def on_game_state_updated(self, league_key: str, team_id: str, state: GameState):
        GLib.idle_add(self.update_display)

    def on_tick(self):
        settings = self.get_settings()
        dash_target = self.plugin_base.sports_service.get_active_dashboard_target()
        page_path = getattr(self.page, "json_path", "") if getattr(self, "page", None) else ""
        is_hub_page = bool(dash_target and "GameHub" in os.path.basename(str(page_path)))
        if is_hub_page:
            league, team_id = dash_target
        else:
            league = settings.get("league", "NFL")
            team_id = str(settings.get("team_id", ""))

        refresh = settings.get("refresh_seconds", 15)
        state = self.plugin_base.sports_service.get_game_state(league, team_id)
        if state and state.status_state == "in":
            refresh = 5

        if league and team_id:
            self.plugin_base.sports_service.fetch_async(league, team_id, force=False, refresh_seconds=refresh)
            if is_hub_page and state and state.status_state == "in" and state.event_id:
                self.plugin_base.sports_service.fetch_game_summary(league, team_id, force=False, refresh_seconds=5)

    def get_deck_controller_to_use(self):
        if getattr(self, "deck_controller", None):
            return self.deck_controller
        if hasattr(gl, "deck_manager") and getattr(gl.deck_manager, "deck_controller", None):
            controllers = gl.deck_manager.deck_controller
            if controllers:
                return controllers[0]
        return None

    def on_key_down(self):
        settings = self.get_settings()
        league = settings.get("league", "NFL")
        team_id = str(settings.get("team_id", ""))
        if league and team_id:
            self.plugin_base.sports_service.set_active_dashboard_target(league, team_id)
            self.plugin_base.sports_service.fetch_async(league, team_id, force=True)
            self.plugin_base.sports_service.fetch_game_summary(league, team_id, force=True)

    def event_callback(self, event, data=None):
        super().event_callback(event, data)
        if event == Input.Key.Events.SHORT_UP:
            self.on_short_tap()
        elif event == Input.Key.Events.HOLD_START:
            self.on_key_hold()

    def on_short_tap(self):
        settings = self.get_settings()
        league = settings.get("league", "NFL")
        team_id = str(settings.get("team_id", ""))
        tap_mode = settings.get("tap_mode", 0)

        if league and team_id:
            self.plugin_base.sports_service.set_active_dashboard_target(league, team_id)
            self.plugin_base.sports_service.fetch_async(league, team_id, force=True)
            self.plugin_base.sports_service.fetch_game_summary(league, team_id, force=True)

        if tap_mode == 0:
            controller = self.get_deck_controller_to_use()
            if not controller:
                return

            # If already on the Game Hub page, do not reload/switch pages
            active_page = getattr(controller, "active_page", None)
            active_path = getattr(active_page, "json_path", "") if active_page else ""
            if active_path and "GameHub" in os.path.basename(str(active_path)):
                return

            key_count = 15
            if hasattr(controller, "deck") and hasattr(controller.deck, "key_count"):
                try:
                    key_count = controller.deck.key_count()
                except Exception:
                    pass
            elif hasattr(controller, "inputs") and Input.Key in controller.inputs:
                key_count = len(controller.inputs[Input.Key])

            is_xl = (key_count >= 32)
            page_filename = "DeckSports_GameHub_XL.json" if is_xl else "DeckSports_GameHub_MK2.json"
            user_page_path = os.path.join(gl.DATA_PATH, "pages", page_filename)

            if not os.path.isfile(user_page_path):
                plugin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                bundled_path = os.path.join(plugin_dir, "pages", page_filename)
                if os.path.isfile(bundled_path):
                    user_page_path = bundled_path

            if os.path.isfile(user_page_path):
                origin = getattr(self, "page", None) or getattr(controller, "active_page", None)
                if origin is not None:
                    json_path = getattr(origin, "json_path", "")
                    if not ("GameHub" in os.path.basename(str(json_path))):
                        self.plugin_base.sports_service.set_origin_page(id(controller), origin)

                page_obj = gl.page_manager.get_page(user_page_path, deck_controller=controller)
                if page_obj:
                    controller.load_page(page_obj)

    def on_key_hold(self):
        settings = self.get_settings()
        coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team_id, _ = self.plugin_base.sports_service.get_nearest_hub_target(coords)
        league = settings.get("league") or hub_league
        team_id = str(settings.get("team_id") or hub_team_id)
        hold_mode = settings.get("hold_mode", "espn")
        custom_url = settings.get("custom_url", "").strip()

        target_url = "https://www.espn.com"

        if hold_mode == "custom" and custom_url:
            target_url = custom_url if custom_url.startswith(("http://", "https://")) else f"https://{custom_url}"
        elif hold_mode == "league":
            target_url = LEAGUE_URLS.get(league, "https://www.espn.com")
        else:
            # ESPN Gamecast / Match Center
            cfg = LEAGUES.get(league)
            sport_slug = cfg.sport_slug if cfg else "sports"
            league_slug = cfg.league_slug if cfg else ""
            state = self.plugin_base.sports_service.get_game_state(league, team_id)

            if state and state.event_id:
                if league in ("MLS",):
                    target_url = f"https://www.espn.com/soccer/match/_/gameId/{state.event_id}"
                else:
                    target_url = f"https://www.espn.com/{sport_slug}/game/_/gameId/{state.event_id}"
            elif team_id:
                target_url = f"https://www.espn.com/{sport_slug}/team/_/id/{team_id}"
            else:
                target_url = f"https://www.espn.com/{sport_slug}/{league_slug}"

        threading.Thread(target=webbrowser.open, args=(target_url,), daemon=True).start()

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

        # 5. Key Tap Behavior (Dashboard vs Refresh)
        tap_model = Gtk.StringList()
        tap_model.append("Open Game Hub Dashboard (MK.2 / XL Page)")
        tap_model.append("Force Refresh Only")

        self._tap_row = Adw.ComboRow(
            title="Key Press Action",
            subtitle="Open full-screen Game Hub or refresh score",
            model=tap_model
        )
        saved_tap = settings.get("tap_mode", 0)
        self._tap_row.set_selected(min(saved_tap, 1))
        self._tap_row.connect("notify::selected", self._on_tap_mode_changed)
        rows.append(self._tap_row)

        # 6. Key Hold Action (Web Destination)
        hold_model = Gtk.StringList()
        for label, _ in HOLD_DESTINATIONS:
            hold_model.append(label)

        self._hold_row = Adw.ComboRow(
            title="Key Hold Webcast Action",
            subtitle="Website opened when key is held for > 500ms",
            model=hold_model
        )
        saved_hold = settings.get("hold_mode", "espn")
        hold_idx = next((i for i, (_, m) in enumerate(HOLD_DESTINATIONS) if m == saved_hold), 0)
        self._hold_row.set_selected(hold_idx)
        self._hold_row.connect("notify::selected", self._on_hold_mode_changed)
        rows.append(self._hold_row)

        self._custom_url_row = Adw.EntryRow(
            title="Custom Web URL",
            text=settings.get("custom_url", "")
        )
        self._custom_url_row.set_visible(saved_hold == "custom")
        self._custom_url_row.connect("changed", self._on_custom_url_changed)
        rows.append(self._custom_url_row)

        # 7. Score Celebration On/Off Toggle
        self._celebration_row = Adw.SwitchRow(
            title="Score Celebration Animations",
            subtitle="Play full-deck celebration when followed team scores (Game Hub page only)"
        )
        self._celebration_row.set_active(settings.get("enable_celebrations", True))
        self._celebration_row.connect("notify::active", self._on_celebration_toggled)
        rows.append(self._celebration_row)

        # 8. Test Celebration Row
        test_row = Adw.ActionRow(
            title="Score Celebration Preview",
            subtitle="Trigger a 3-second full-deck animation for followed team"
        )
        test_btn = Gtk.Button(label="Play Animation")
        test_btn.set_valign(Gtk.Align.CENTER)
        test_btn.connect("clicked", self._on_test_celebration_clicked)
        test_row.add_suffix(test_btn)
        rows.append(test_row)

        # 9. Test Victory Jumbotron Row
        test_vic_row = Adw.ActionRow(
            title="Victory Celebration Preview",
            subtitle="Trigger a 4-second victory confetti & fireworks animation"
        )
        test_vic_btn = Gtk.Button(label="Play Victory")
        test_vic_btn.set_valign(Gtk.Align.CENTER)
        test_vic_btn.connect("clicked", self._on_test_victory_clicked)
        test_vic_row.add_suffix(test_vic_btn)
        rows.append(test_vic_row)

        return rows

    def _on_hold_mode_changed(self, row, _pspec):
        idx = row.get_selected()
        if 0 <= idx < len(HOLD_DESTINATIONS):
            _, mode_val = HOLD_DESTINATIONS[idx]
            settings = self.get_settings()
            settings["hold_mode"] = mode_val
            self.set_settings(settings)
            if hasattr(self, "_custom_url_row") and self._custom_url_row:
                self._custom_url_row.set_visible(mode_val == "custom")

    def _on_custom_url_changed(self, row):
        settings = self.get_settings()
        settings["custom_url"] = row.get_text().strip()
        self.set_settings(settings)

    def _on_celebration_toggled(self, row, _pspec):
        settings = self.get_settings()
        settings["enable_celebrations"] = row.get_active()
        self.set_settings(settings)

    def _on_test_celebration_clicked(self, _btn):
        settings = self.get_settings()
        coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team_id, _ = self.plugin_base.sports_service.get_nearest_hub_target(coords)
        league = settings.get("league") or hub_league
        team_id = str(settings.get("team_id") or hub_team_id)

        state = self.plugin_base.sports_service.get_game_state(league, team_id)
        team = state.away_team if (state.followed_team_id and str(state.away_team.id) == str(state.followed_team_id)) else state.home_team
        team_name = team.name if team.name else "Followed Team"
        team_abbrev = team.abbreviation if team.abbreviation else "TEAM"
        p_color = team.color if team.color else (0, 53, 148, 255)
        alt_color = team.alternate_color if team.alternate_color else (200, 205, 215, 255)

        if hasattr(self.plugin_base.sports_service, "celebration_manager"):
            self.plugin_base.sports_service.celebration_manager.trigger(
                league_key=league,
                team_name=team_name,
                team_abbrev=team_abbrev,
                primary_color=p_color,
                alt_color=alt_color,
                force_preview=True
            )

    def _on_test_victory_clicked(self, _btn):
        settings = self.get_settings()
        coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team_id, _ = self.plugin_base.sports_service.get_nearest_hub_target(coords)
        league = settings.get("league") or hub_league
        team_id = str(settings.get("team_id") or hub_team_id)

        state = self.plugin_base.sports_service.get_game_state(league, team_id)
        team = state.away_team if (state.followed_team_id and str(state.away_team.id) == str(state.followed_team_id)) else state.home_team
        opp = state.home_team if team == state.away_team else state.away_team
        team_name = team.name if team.name else "Followed Team"
        team_abbrev = team.abbreviation if team.abbreviation else "TEAM"
        p_color = team.color if team.color else (0, 53, 148, 255)
        alt_color = team.alternate_color if team.alternate_color else (200, 205, 215, 255)

        my_sc = team.score if team.score else "28"
        opp_sc = opp.score if opp.score else "21"
        opp_abbrev = opp.abbreviation if opp.abbreviation else "OPP"

        if hasattr(self.plugin_base.sports_service, "celebration_manager"):
            self.plugin_base.sports_service.celebration_manager.trigger_victory(
                league_key=league,
                team_name=team_name,
                team_abbrev=team_abbrev,
                primary_color=p_color,
                alt_color=alt_color,
                my_score=my_sc,
                opp_abbrev=opp_abbrev,
                opp_score=opp_sc,
                force_preview=True
            )

    def _on_tap_mode_changed(self, row, _pspec):
        idx = row.get_selected()
        settings = self.get_settings()
        settings["tap_mode"] = idx
        self.set_settings(settings)

    def _populate_team_dropdown(self, league_key: str, initial_select: str = ""):
        self._is_updating_ui = True
        self._current_team_list = self.plugin_base.sports_service.get_teams(league_key)

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

            self._populate_team_dropdown(new_league)
            if self._current_team_list:
                first_team_id = str(self._current_team_list[0]["id"])
                settings["team_id"] = first_team_id
            self.set_settings(settings)

            coords = getattr(self.input_ident, "coords", None)
            display_mode = settings.get("display_mode", 0)
            team_id = str(settings.get("team_id", ""))
            self.plugin_base.sports_service.set_active_dashboard_target(new_league, team_id)
            self.plugin_base.sports_service.register_hub(id(self), coords, new_league, team_id, display_mode, action_obj=self)
            self.plugin_base.sports_service.fetch_async(new_league, team_id, force=True)
            self.plugin_base.sports_service.fetch_game_summary(new_league, team_id, force=True)
            self.plugin_base.sports_service.notify_all()
            self.update_display()

    def _on_team_changed(self, row, _pspec):
        if self._is_updating_ui:
            return
        idx = row.get_selected()
        if 0 <= idx < len(self._current_team_list):
            team_obj = self._current_team_list[idx]
            settings = self.get_settings()
            team_id = str(team_obj["id"])
            settings["team_id"] = team_id
            self.set_settings(settings)

            coords = getattr(self.input_ident, "coords", None)
            display_mode = settings.get("display_mode", 0)
            league = settings.get("league", "NFL")
            self.plugin_base.sports_service.set_active_dashboard_target(league, team_id)
            self.plugin_base.sports_service.register_hub(id(self), coords, league, team_id, display_mode, action_obj=self)
            self.plugin_base.sports_service.fetch_async(league, team_id, force=True)
            self.plugin_base.sports_service.fetch_game_summary(league, team_id, force=True)
            self.plugin_base.sports_service.notify_all()
            self.update_display()

    def _on_refresh_changed(self, row, _pspec):
        idx = row.get_selected()
        if 0 <= idx < len(REFRESH_OPTIONS):
            _, seconds = REFRESH_OPTIONS[idx]
            settings = self.get_settings()
            settings["refresh_seconds"] = seconds
            self.set_settings(settings)

    def _on_display_mode_changed(self, row, _pspec):
        idx = row.get_selected()
        settings = self.get_settings()
        settings["display_mode"] = idx
        self.set_settings(settings)

        coords = getattr(self.input_ident, "coords", None)
        self.plugin_base.sports_service.register_hub(id(self), coords, settings.get("league", "NFL"), str(settings.get("team_id", "")), idx)
        self.update_display()

    # --- Canvas Rendering with Pillow ---
    def update_display(self):
        if not self.get_is_present():
            return
        self._ensure_media_control()

        settings = self.get_settings()
        dash_target = self.plugin_base.sports_service.get_active_dashboard_target()
        page_path = getattr(self.page, "json_path", "") if getattr(self, "page", None) else ""
        if dash_target and "GameHub" in os.path.basename(str(page_path)):
            league, team_id = dash_target
        else:
            league = settings.get("league", "NFL")
            team_id = str(settings.get("team_id", ""))

        state = self.plugin_base.sports_service.get_game_state(league, team_id)
        has_score_keys = self.plugin_base.sports_service.has_score_actions()

        # Dynamically manage 1-second ticking timer for live game state
        is_live_clock = (state.status_state == "in" and getattr(state, "clock_is_running", False))
        self._manage_clock_timer(is_live_clock)

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
            # LIVE GAME STATE (With smooth 1-second interpolated ticking clock)
            clock_text = self.plugin_base.sports_service.get_interpolated_clock(state)
            period_str = f"Q{state.period}" if state.period and state.league_key in ("NFL", "NBA", "UFL") else state.period_text

            font_period = get_bundled_font(13)
            font_clock = get_bundled_font(16)
            draw.text((50, 42), period_str, fill=(255, 210, 50, 255), anchor="mm", font=font_period)
            draw.text((50, 59), clock_text, fill=(255, 255, 255, 255), anchor="mm", font=font_clock)

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
            if has_score_keys:
                # 3-BUTTON SCOREBOARD MODE: Clean bold badge
                font_final = get_bundled_font(21)
                final_text = "FINAL / OT" if ("ot" in state.status_detail.lower() or "overtime" in state.status_detail.lower()) else "FINAL"
                draw.text((50, 62), final_text, fill=(255, 65, 65, 255), anchor="mm", font=font_final)
            else:
                # STANDALONE 1-BUTTON MODE: Show status, scores, and mini logos
                font_status = get_bundled_font(13)
                font_score = get_bundled_font(15)
                font_det = get_bundled_font(11)

                final_text = "FINAL / OT" if ("ot" in state.status_detail.lower() or "overtime" in state.status_detail.lower()) else "FINAL"
                draw.text((50, 41), final_text, fill=(255, 75, 75, 255), anchor="mm", font=font_status)

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
