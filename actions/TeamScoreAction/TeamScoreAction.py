"""
DeckSports TeamScoreAction
Displays live score, team logo, record, and color branding for Team A (Away) or Team B (Home).
"""

import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from src.backend.PluginManager.ActionBase import ActionBase
from ...backend.SportsService import GameState, TeamInfo

SIDE_OPTIONS = [
    ("Auto (Sync with Game Hub: Left=Away, Right=Home)", "auto"),
    ("Team A / Away (Visiting Team)", "away"),
    ("Team B / Home (Host Team)", "home"),
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

class TeamScoreAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._side_row: Adw.ComboRow | None = None

    def on_ready(self):
        self.plugin_base.sports_service.add_listener(self.on_game_state_updated)
        self.update_display()

    def on_game_state_updated(self, state: GameState):
        GLib.idle_add(self.update_display)

    def on_key_down(self):
        self.plugin_base.sports_service.fetch_async()

    # --- Sidebar Configuration UI ---
    def get_config_rows(self) -> list:
        side_model = Gtk.StringList()
        for label, _ in SIDE_OPTIONS:
            side_model.append(label)

        self._side_row = Adw.ComboRow(
            title="Team Slot / Side",
            subtitle="Auto mode synchronizes relative to the Game Hub button",
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

    def _resolve_team_info(self, state: GameState) -> TeamInfo:
        settings = self.get_settings()
        side_setting = settings.get("side", "auto")

        # Explicit manual overrides
        if side_setting == "away":
            return state.away_team
        elif side_setting == "home":
            return state.home_team

        # AUTO MODE: Compare horizontal position relative to Game Hub
        hub_coords = self.plugin_base.sports_service.hub_coords
        my_coords = getattr(self.input_ident, "coords", None)

        if hub_coords and my_coords and isinstance(my_coords, (list, tuple)) and len(my_coords) >= 2:
            my_x = my_coords[0]
            hub_x = hub_coords[0]

            # Right of the Game Hub -> Home Team
            if my_x > hub_x:
                return state.home_team
            # Left of the Game Hub -> Away Team
            elif my_x < hub_x:
                return state.away_team

        # Fallback if coordinates cannot be compared
        return state.away_team

    # --- Canvas Rendering with Pillow ---
    def update_display(self):
        state = self.plugin_base.sports_service.active_game_state
        team = self._resolve_team_info(state)

        img = Image.new("RGBA", (100, 100), (22, 24, 30, 255))
        draw = ImageDraw.Draw(img)

        # 1. Header Banner with team primary color
        header_color = team.color if team.color else (45, 50, 60, 255)
        draw.rectangle([(0, 0), (100, 26)], fill=header_color)
        draw.line([(0, 26), (100, 26)], fill=(255, 255, 255, 40), width=1)

        # Team abbreviation in header
        font_header = get_bundled_font(13)
        draw.text((10, 13), team.abbreviation, fill=(255, 255, 255, 255), anchor="lm", font=font_header)

        # Home / Away indicator tag
        tag = "HOME" if team.is_home else "AWAY"
        font_tag = get_bundled_font(9)
        draw.text((90, 13), tag, fill=(240, 240, 240, 210), anchor="rm", font=font_tag)

        # 2. Team Logo in Center Background (Faded / Watermark style)
        if team.logo_url:
            logo = self.plugin_base.sports_service.get_image(team.logo_url, max_size=(56, 56))
            if logo:
                alpha = logo.split()[3]
                alpha = ImageEnhance.Brightness(alpha).enhance(0.40)
                faded_logo = logo.copy()
                faded_logo.putalpha(alpha)

                lx = (100 - faded_logo.width) // 2
                ly = 26 + (50 - faded_logo.height) // 2
                img.alpha_composite(faded_logo, (lx, ly))

        # 3. BIG CENTERED SCORE (Large 34px bold font)
        score_val = team.score if (state.status_state in ("in", "post") and team.score is not None) else "0"
        if state.status_state in ("pre", "off") and (not team.score or team.score == "0"):
            score_val = "—"

        font_score = get_bundled_font(34)
        cx, cy = 50, 52

        # Draw dark outline around score text for guaranteed legibility
        outline_color = (10, 10, 15, 250)
        for ox in (-2, -1, 0, 1, 2):
            for oy in (-2, -1, 0, 1, 2):
                if ox != 0 or oy != 0:
                    draw.text((cx + ox, cy + oy), score_val, fill=outline_color, anchor="mm", font=font_score)

        # Main score text
        draw.text((cx, cy), score_val, fill=(255, 255, 255, 255), anchor="mm", font=font_score)

        # 4. Footer Bar: Record / Status
        draw.rectangle([(0, 78), (100, 100)], fill=(16, 18, 22, 255))
        draw.line([(0, 78), (100, 78)], fill=(45, 50, 60, 255), width=1)

        font_footer = get_bundled_font(11)
        footer_text = team.record if team.record else team.short_name
        draw.text((50, 89), footer_text[:14], fill=(180, 190, 205, 255), anchor="mm", font=font_footer)

        # Outer key border
        draw.rectangle([(0, 0), (99, 99)], outline=(50, 55, 68, 255), width=1)

        self.set_media(image=img)
