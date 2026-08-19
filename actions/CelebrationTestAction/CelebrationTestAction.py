"""
DeckSports CelebrationTestAction
Test trigger key to fire a full-deck score celebration animation tied to the followed/home team.
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
    from ...backend.SportsService import GameState
except (ImportError, ValueError):
    from backend.SportsService import GameState

@lru_cache(maxsize=32)
def get_bundled_font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    plugin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    bundled_font = os.path.join(plugin_dir, "assets", "fonts", "ScoreFont-Bold.ttf")
    if os.path.exists(bundled_font):
        try:
            return ImageFont.truetype(bundled_font, size)
        except Exception:
            pass
    return ImageFont.load_default()

class CelebrationTestAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
        GLib.idle_add(self.update_display)

    def on_remove(self):
        self.plugin_base.sports_service.remove_listener(self.on_game_state_updated)

    def on_game_state_updated(self, league_key: str, team_id: str, state: GameState):
        GLib.idle_add(self.update_display)

    def on_key_down(self):
        # Resolve target team from nearest hub or active target
        my_coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team_id, _ = self.plugin_base.sports_service.get_nearest_hub_target(my_coords)
        state = self.plugin_base.sports_service.get_game_state(hub_league, hub_team_id)

        # Target team is the followed team / home team
        team = state.away_team if (state.followed_team_id and str(state.away_team.id) == str(state.followed_team_id)) else state.home_team
        team_name = team.name if team.name else "Cowboys"
        team_abbrev = team.abbreviation if team.abbreviation else "DAL"
        p_color = team.color if team.color else (0, 53, 148, 255)
        alt_color = team.alternate_color if team.alternate_color else (200, 205, 215, 255)

        if hasattr(self.plugin_base.sports_service, "celebration_manager"):
            self.plugin_base.sports_service.celebration_manager.trigger(
                league_key=hub_league,
                team_name=team_name,
                team_abbrev=team_abbrev,
                primary_color=p_color,
                alt_color=alt_color
            )

    def update_display(self):
        if not self.get_is_present():
            return
        self._ensure_media_control()

        my_coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team_id, _ = self.plugin_base.sports_service.get_nearest_hub_target(my_coords)
        state = self.plugin_base.sports_service.get_game_state(hub_league, hub_team_id)
        team = state.away_team if (state.followed_team_id and str(state.away_team.id) == str(state.followed_team_id)) else state.home_team

        img = Image.new("RGBA", (100, 100), (22, 24, 32, 255))
        draw = ImageDraw.Draw(img)

        # Header banner
        header_color = team.color if team.color else (0, 53, 148, 255)
        draw.rectangle([(0, 0), (100, 24)], fill=header_color)
        draw.line([(0, 24), (100, 24)], fill=(255, 255, 255, 40), width=1)

        font_hdr = get_bundled_font(10)
        draw.text((50, 12), "TEST CELEBRATE", fill=(255, 255, 255, 255), anchor="mm", font=font_hdr)

        # Body: Star / Trophy / Touchdown symbol
        font_main = get_bundled_font(18)
        draw.text((50, 48), "★ GO ★", fill=(255, 215, 0, 255), anchor="mm", font=font_main)

        # Footer: Team Name
        draw.rectangle([(0, 76), (100, 100)], fill=(16, 18, 22, 255))
        draw.line([(0, 76), (100, 76)], fill=(45, 50, 60, 255), width=1)

        font_foot = get_bundled_font(10)
        t_label = team.name if team.name else "Followed Team"
        draw.text((50, 88), t_label[:14], fill=(180, 210, 245, 255), anchor="mm", font=font_foot)

        # Key outline
        draw.rectangle([(0, 0), (99, 99)], outline=(255, 215, 0, 120), width=1)

        self.set_media(image=img)
