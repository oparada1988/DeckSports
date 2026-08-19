"""
DeckSports ScoringSummaryAction
Displays recent scoring play and drive summaries.
"""

import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from PIL import Image, ImageDraw, ImageFont

from src.backend.PluginManager.ActionBase import ActionBase
try:
    from ...backend.SportsService import GameState, GameSummary
except (ImportError, ValueError):
    from backend.SportsService import GameState, GameSummary

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

class ScoringSummaryAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _ensure_media_control(self):
        try:
            input_state = self.get_state()
            if input_state and hasattr(input_state, "action_permission_manager"):
                pm = input_state.action_permission_manager
                curr_idx = pm.get_image_control_index()
                own_idx = self.get_own_action_index()
                if own_idx is not None and (curr_idx is None or curr_idx != own_idx):
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

    def update_display(self):
        self._ensure_media_control()

        my_coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team_id, _ = self.plugin_base.sports_service.get_nearest_hub_target(my_coords)

        state = self.plugin_base.sports_service.get_game_state(hub_league, hub_team_id)
        summary = self.plugin_base.sports_service.get_game_summary(hub_league, hub_team_id)

        img = Image.new("RGBA", (100, 100), (22, 24, 30, 255))
        draw = ImageDraw.Draw(img)

        # 1. Header Banner
        draw.rectangle([(0, 0), (100, 24)], fill=(35, 42, 54, 255))
        draw.line([(0, 24), (100, 24)], fill=(50, 60, 80, 255), width=1)

        font_hdr = get_bundled_font(10)
        draw.text((50, 12), "SCORING PLAY", fill=(180, 195, 220, 255), anchor="mm", font=font_hdr)

        # 2. Main Body: Last Scoring Play Text
        play_text = summary.last_play if summary.last_play else (f"{state.away_team.abbreviation} vs {state.home_team.abbreviation}")

        font_body = get_bundled_font(10)
        words = play_text.split()
        lines = []
        curr_line = ""
        for w in words:
            if len(curr_line + " " + w) < 14:
                curr_line = (curr_line + " " + w).strip()
            else:
                lines.append(curr_line)
                curr_line = w
        if curr_line:
            lines.append(curr_line)

        y_offset = 36
        for line in lines[:3]:
            draw.text((50, y_offset), line, fill=(255, 255, 255, 255), anchor="mm", font=font_body)
            y_offset += 13

        # 3. Footer Bar: Period / Time
        draw.rectangle([(0, 76), (100, 100)], fill=(16, 18, 22, 255))
        draw.line([(0, 76), (100, 76)], fill=(45, 50, 60, 255), width=1)
        font_foot = get_bundled_font(10)
        draw.text((50, 88), state.clock if state.clock else state.period_text[:14], fill=(255, 210, 60, 255), anchor="mm", font=font_foot)

        draw.rectangle([(0, 0), (99, 99)], outline=(50, 55, 68, 255), width=1)
        self.set_media(image=img)
