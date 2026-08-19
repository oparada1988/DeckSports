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
    ("Auto (Left = Away, Right = Home)", "auto"),
    ("Team A / Away (Left Key)", "away"),
    ("Team B / Home (Right Key)", "home"),
]

def get_font(size: int = 14, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf" if bold else "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
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
            subtitle="Choose whether this key tracks Team A (Away) or Team B (Home)",
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

        # Determine if this action should display away or home team
        if side_setting == "away":
            return state.away_team
        elif side_setting == "home":
            return state.home_team
        else:
            # Auto mode: Determine side from key coordinates if available, or default to away
            coords = getattr(self.input_ident, "coords", None)
            if coords and isinstance(coords, (list, tuple)) and len(coords) >= 2:
                col = coords[1]
                # If column is on the right side of the deck, use home
                if col >= 2:
                    return state.home_team
            return state.away_team

    # --- Canvas Rendering with Pillow ---
    def update_display(self):
        state = self.plugin_base.sports_service.active_game_state
        team = self._resolve_team_info(state)

        img = Image.new("RGBA", (100, 100), (22, 24, 30, 255))
        draw = ImageDraw.Draw(img)

        # 1. Header Banner with team color
        draw.rectangle([(0, 0), (100, 26)], fill=team.color)
        draw.line([(0, 26), (100, 26)], fill=(255, 255, 255, 40), width=1)

        # Team abbreviation in header
        font_header = get_font(13, bold=True)
        draw.text((10, 13), team.abbreviation, fill=(255, 255, 255, 255), anchor="lm", font=font_header)

        # Home / Away indicator tag
        tag = "HOME" if team.is_home else "AWAY"
        font_tag = get_font(9, bold=True)
        draw.text((90, 13), tag, fill=(240, 240, 240, 200), anchor="rm", font=font_tag)

        # 2. Team Logo in Center Background (Faded / Transparent)
        if team.logo_url:
            logo = self.plugin_base.sports_service.get_image(team.logo_url, max_size=(54, 54))
            if logo:
                # Dim / blend the logo so the score text pops cleanly
                alpha = logo.split()[3]
                alpha = ImageEnhance.Brightness(alpha).enhance(0.45)
                faded_logo = logo.copy()
                faded_logo.putalpha(alpha)

                lx = (100 - faded_logo.width) // 2
                ly = 26 + (50 - faded_logo.height) // 2
                img.alpha_composite(faded_logo, (lx, ly))

        # 3. BIG CENTERED SCORE
        score_val = team.score if (state.status_state in ("in", "post") and team.score is not None) else "0"
        if state.status_state in ("pre", "off") and not (team.score and team.score != "0"):
            score_val = "—"

        font_score = get_font(34, bold=True)
        cx, cy = 50, 52

        # Draw dark drop-shadow outline around score text for high contrast
        outline_color = (10, 10, 15, 240)
        for ox in (-2, -1, 0, 1, 2):
            for oy in (-2, -1, 0, 1, 2):
                if ox != 0 or oy != 0:
                    draw.text((cx + ox, cy + oy), score_val, fill=outline_color, anchor="mm", font=font_score)

        # Main score text
        draw.text((cx, cy), score_val, fill=(255, 255, 255, 255), anchor="mm", font=font_score)

        # 4. Footer Bar: Record / Status
        draw.rectangle([(0, 78), (100, 100)], fill=(16, 18, 22, 255))
        draw.line([(0, 78), (100, 78)], fill=(45, 50, 60, 255), width=1)

        font_footer = get_font(11, bold=False)
        footer_text = team.record if team.record else team.short_name
        draw.text((50, 89), footer_text[:14], fill=(180, 190, 205, 255), anchor="mm", font=font_footer)

        # Outer key border
        draw.rectangle([(0, 0), (99, 99)], outline=(50, 55, 68, 255), width=1)

        self.set_media(image=img)
