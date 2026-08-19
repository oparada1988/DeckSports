"""
DeckSports TeamScoreAction
Displays live score, team logo, record, and color branding for Team A (Away) or Team B (Home).
Automatically pairs with the nearest Game Hub on the same row and defaults media control.
"""

import os
from functools import lru_cache
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from src.backend.PluginManager.ActionBase import ActionBase
try:
    from ...backend.SportsService import GameState, TeamInfo
except (ImportError, ValueError):
    from backend.SportsService import GameState, TeamInfo

SIDE_OPTIONS = [
    ("Auto (Sync with nearest Game Hub on row: Left=Away, Right=Home)", "auto"),
    ("Team A / Away (Visiting Team)", "away"),
    ("Team B / Home (Host Team)", "home"),
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

class TeamScoreAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._side_row: Adw.ComboRow | None = None

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
        self.plugin_base.sports_service.register_score_action(id(self))
        self.plugin_base.sports_service.add_listener(self.on_game_state_updated)
        GLib.idle_add(self.update_display)

    def on_remove(self):
        self.plugin_base.sports_service.unregister_score_action(id(self))
        self.plugin_base.sports_service.remove_listener(self.on_game_state_updated)

    def on_game_state_updated(self, league_key: str, team_id: str, state: GameState):
        GLib.idle_add(self.update_display)

    def on_key_down(self):
        my_coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team, _ = self.plugin_base.sports_service.get_nearest_hub_target(my_coords)
        if hub_league and hub_team:
            self.plugin_base.sports_service.fetch_async(hub_league, hub_team, force=True)

    # --- Sidebar Configuration UI ---
    def get_config_rows(self) -> list:
        side_model = Gtk.StringList()
        for label, _ in SIDE_OPTIONS:
            side_model.append(label)

        self._side_row = Adw.ComboRow(
            title="Team Slot / Side",
            subtitle="Auto pairs with the Game Hub on the same row",
            model=side_model
        )

        settings = self.get_settings()
        saved_side = settings.get("side", "auto")
        side_idx = next((i for i, (_, s) in enumerate(SIDE_OPTIONS) if s == saved_side), 0)
        self._side_row.set_selected(side_idx)
        self._side_row.connect("notify::selected", self._on_side_changed)

        return [self._side_row]

    def _on_side_changed(self, row, _pspec):
        idx = row.get_selected()
        if 0 <= idx < len(SIDE_OPTIONS):
            _, side_val = SIDE_OPTIONS[idx]
            settings = self.get_settings()
            settings["side"] = side_val
            self.set_settings(settings)
            self.update_display()

    def _resolve_team_and_state(self) -> tuple[GameState, TeamInfo]:
        settings = self.get_settings()
        side_setting = settings.get("side", "auto")

        my_coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team_id, auto_side = self.plugin_base.sports_service.get_nearest_hub_target(my_coords)

        state = self.plugin_base.sports_service.get_game_state(hub_league, hub_team_id)

        chosen_side = auto_side if side_setting == "auto" else side_setting

        if chosen_side == "home":
            team = state.home_team
        elif chosen_side == "away":
            team = state.away_team
        elif chosen_side == "followed":
            team = state.away_team if str(state.away_team.id) == str(state.followed_team_id) else state.home_team
        elif chosen_side == "opponent":
            team = state.home_team if str(state.away_team.id) == str(state.followed_team_id) else state.away_team
        else:
            team = state.away_team

        return state, team

    # --- Canvas Rendering with Pillow ---
    def update_display(self):
        if not self.get_is_present():
            return
        self._ensure_media_control()

        state, team = self._resolve_team_and_state()

        img = Image.new("RGBA", (100, 100), (22, 24, 30, 255))
        draw = ImageDraw.Draw(img)

        # 1. Header Banner with team primary color
        header_color = team.color if team.color else (45, 45, 45, 255)
        draw.rectangle([(0, 0), (100, 26)], fill=header_color)
        draw.line([(0, 26), (100, 26)], fill=(255, 255, 255, 40), width=1)

        # Team abbreviation in header
        font_header = get_bundled_font(13)
        draw.text((10, 13), team.abbreviation, fill=(255, 255, 255, 255), anchor="lm", font=font_header)

        # Home / Away indicator tag
        tag = "HOME" if team.is_home else "AWAY"
        font_tag = get_bundled_font(9)
        draw.text((90, 13), tag, fill=(240, 240, 240, 210), anchor="rm", font=font_tag)

        # 2. Main Body: Live/Recent Final Score vs Pre-Game/Off-Season Team Display
        is_live_or_recent_final = (state.status_state in ("in", "post"))

        if is_live_or_recent_final:
            # Watermark logo behind score
            if team.logo_url:
                logo = self.plugin_base.sports_service.get_image(team.logo_url, max_size=(56, 56))
                if logo:
                    alpha = logo.split()[3]
                    alpha = ImageEnhance.Brightness(alpha).enhance(0.35)
                    faded_logo = logo.copy()
                    faded_logo.putalpha(alpha)

                    lx = (100 - faded_logo.width) // 2
                    ly = 26 + (50 - faded_logo.height) // 2
                    img.alpha_composite(faded_logo, (lx, ly))

            # BIG CENTERED SCORE (Large 34px bold font)
            score_val = team.score if (team.score is not None and team.score != "") else "0"
            font_score = get_bundled_font(34)
            cx, cy = 50, 52

            # Draw dark outline around score text for high contrast
            outline_color = (10, 10, 15, 250)
            for ox in (-2, -1, 0, 1, 2):
                for oy in (-2, -1, 0, 1, 2):
                    if ox != 0 or oy != 0:
                        draw.text((cx + ox, cy + oy), score_val, fill=outline_color, anchor="mm", font=font_score)

            # Main score text
            draw.text((cx, cy), score_val, fill=(255, 255, 255, 255), anchor="mm", font=font_score)
        else:
            # UPCOMING PRE-GAME / OFF-SEASON: No score shown! Crisp centered team logo
            if team.logo_url:
                logo = self.plugin_base.sports_service.get_image(team.logo_url, max_size=(50, 50))
                if logo:
                    lx = (100 - logo.width) // 2
                    ly = 26 + (52 - logo.height) // 2
                    img.alpha_composite(logo, (lx, ly))
            else:
                font_name = get_bundled_font(12)
                draw.text((50, 52), team.short_name[:8], fill=(220, 225, 235, 255), anchor="mm", font=font_name)

        # 3. Footer Bar: Record / Status
        draw.rectangle([(0, 78), (100, 100)], fill=(16, 18, 22, 255))
        draw.line([(0, 78), (100, 78)], fill=(45, 50, 60, 255), width=1)

        font_footer = get_bundled_font(11)
        footer_text = team.record if team.record else team.short_name
        draw.text((50, 89), footer_text[:14], fill=(180, 190, 205, 255), anchor="mm", font=font_footer)

        # Outer key border
        draw.rectangle([(0, 0), (99, 99)], outline=(50, 55, 68, 255), width=1)

        self.set_media(image=img)
