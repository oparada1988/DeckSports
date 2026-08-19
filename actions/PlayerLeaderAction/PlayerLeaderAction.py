"""
DeckSports PlayerLeaderAction
Displays category leader card with circular athlete headshots, names, and live performance metrics.
"""

import os
from functools import lru_cache
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from PIL import Image, ImageDraw, ImageFont

from src.backend.PluginManager.ActionBase import ActionBase
try:
    from ...backend.SportsService import GameState, GameSummary, PlayerLeader
except (ImportError, ValueError):
    from backend.SportsService import GameState, GameSummary, PlayerLeader

SIDE_OPTIONS = [
    ("Auto (Sync with nearest Game Hub on row)", "auto"),
    ("Away Team Leader", "away"),
    ("Home Team Leader", "home"),
]

CATEGORY_OPTIONS = [
    ("Primary Leader (Passing / Batting / Points)", 0),
    ("Secondary Leader (Rushing / Pitching / Rebounds)", 1),
    ("Tertiary Leader (Receiving / Defense / Assists)", 2),
]

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

class PlayerLeaderAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._side_row: Adw.ComboRow | None = None
        self._cat_row: Adw.ComboRow | None = None

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

    def on_ready(self):
        self._ensure_media_control()
        self.plugin_base.sports_service.add_listener(self.on_game_state_updated)
        self.update_display()

    def on_remove(self):
        self.plugin_base.sports_service.remove_listener(self.on_game_state_updated)

    def on_game_state_updated(self, league_key: str, team_id: str, state: GameState):
        GLib.idle_add(self.update_display)

    def on_key_down(self):
        my_coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team, _ = self.plugin_base.sports_service.get_nearest_hub_target(my_coords)
        if hub_league and hub_team:
            self.plugin_base.sports_service.fetch_game_summary(hub_league, hub_team, force=True)

    def get_config_rows(self) -> list:
        rows = []

        side_model = Gtk.StringList()
        for label, _ in SIDE_OPTIONS:
            side_model.append(label)

        self._side_row = Adw.ComboRow(
            title="Team Side",
            subtitle="Auto selects Away/Home depending on placement",
            model=side_model
        )
        settings = self.get_settings()
        saved_side = settings.get("side", "auto")
        side_idx = next((i for i, (_, s) in enumerate(SIDE_OPTIONS) if s == saved_side), 0)
        self._side_row.set_selected(side_idx)
        self._side_row.connect("notify::selected", self._on_side_changed)
        rows.append(self._side_row)

        cat_model = Gtk.StringList()
        for label, _ in CATEGORY_OPTIONS:
            cat_model.append(label)

        self._cat_row = Adw.ComboRow(
            title="Leader Category Rank",
            subtitle="Primary, Secondary, or Tertiary category leader",
            model=cat_model
        )
        saved_cat = settings.get("cat_idx", 0)
        self._cat_row.set_selected(saved_cat)
        self._cat_row.connect("notify::selected", self._on_cat_changed)
        rows.append(self._cat_row)

        return rows

    def _on_side_changed(self, row, _pspec):
        idx = row.get_selected()
        if 0 <= idx < len(SIDE_OPTIONS):
            _, side_val = SIDE_OPTIONS[idx]
            settings = self.get_settings()
            settings["side"] = side_val
            self.set_settings(settings)
            self.update_display()

    def _on_cat_changed(self, row, _pspec):
        idx = row.get_selected()
        settings = self.get_settings()
        settings["cat_idx"] = idx
        self.set_settings(settings)
        self.update_display()

    def update_display(self):
        if not self.get_is_present():
            return
        self._ensure_media_control()

        my_coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team_id, auto_side = self.plugin_base.sports_service.get_nearest_hub_target(my_coords)

        state = self.plugin_base.sports_service.get_game_state(hub_league, hub_team_id)
        summary = self.plugin_base.sports_service.get_game_summary(hub_league, hub_team_id)

        settings = self.get_settings()
        side_setting = settings.get("side", "auto")
        chosen_side = auto_side if side_setting == "auto" else side_setting

        team = state.home_team if chosen_side in ("home", "opponent") else state.away_team
        leaders = summary.home_leaders if chosen_side in ("home", "opponent") else summary.away_leaders

        cat_idx = settings.get("cat_idx", 0)
        leader = leaders[cat_idx] if len(leaders) > cat_idx else None

        img = Image.new("RGBA", (100, 100), (22, 24, 30, 255))
        draw = ImageDraw.Draw(img)

        # 1. Header Banner
        header_color = team.color if team.color else (45, 45, 45, 255)
        draw.rectangle([(0, 0), (100, 24)], fill=header_color)
        draw.line([(0, 24), (100, 24)], fill=(255, 255, 255, 40), width=1)

        font_hdr = get_bundled_font(11)
        cat_title = leader.category.upper() if leader else "LEADER"
        draw.text((50, 12), f"{team.abbreviation} {cat_title}"[:15], fill=(255, 255, 255, 255), anchor="mm", font=font_hdr)

        # 2. Body: Athlete Headshot + Name
        if leader and leader.headshot_url:
            hs = self.plugin_base.sports_service.get_headshot(leader.headshot_url, max_size=(34, 34))
            if hs:
                img.alpha_composite(hs, (8, 32))
            else:
                draw.ellipse([(8, 32), (42, 66)], fill=(38, 44, 58, 255), outline=(70, 80, 105, 255))
        elif team.logo_url:
            mini_logo = self.plugin_base.sports_service.get_image(team.logo_url, max_size=(32, 32))
            if mini_logo:
                img.alpha_composite(mini_logo, (8, 33))

        font_name = get_bundled_font(11)
        font_stat = get_bundled_font(10)

        p_name = leader.name if leader else team.short_name
        # Render name next to avatar
        draw.text((46, 42), p_name[:9], fill=(255, 255, 255, 255), anchor="lm", font=font_name)
        if leader and leader.jersey:
            draw.text((46, 56), f"#{leader.jersey}", fill=(255, 210, 60, 255), anchor="lm", font=font_stat)

        # 3. Footer Bar: Stat value
        draw.rectangle([(0, 76), (100, 100)], fill=(16, 18, 22, 255))
        draw.line([(0, 76), (100, 76)], fill=(45, 50, 60, 255), width=1)

        stat_text = leader.display_stat if (leader and leader.display_stat) else team.record
        draw.text((50, 88), stat_text[:16], fill=(180, 200, 230, 255), anchor="mm", font=font_stat)

        draw.rectangle([(0, 0), (99, 99)], outline=(50, 55, 68, 255), width=1)
        self.set_media(image=img)
