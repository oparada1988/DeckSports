"""
DeckSports SituationAction
Displays situational radar cards (Down & Dist, Red Zone, Count/Outs, Power Play, Venue/TV/Weather).
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

SITUATION_MODES = [
    ("Auto / Contextual Radar", "auto"),
    ("Down & Dist / Count & Outs", "down_dist"),
    ("Ball Spot / Red Zone / Base Runners", "ball_spot"),
    ("Drive Info / Power Play / Dominance", "drive_pp"),
    ("Venue / TV / Weather", "venue_tv"),
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

class SituationAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mode_row: Adw.ComboRow | None = None

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

    def get_config_rows(self) -> list:
        mode_model = Gtk.StringList()
        for label, _ in SITUATION_MODES:
            mode_model.append(label)

        self._mode_row = Adw.ComboRow(
            title="Radar Card Display Mode",
            subtitle="Choose what situational data to present on this tile",
            model=mode_model
        )

        settings = self.get_settings()
        saved_mode = settings.get("mode", "auto")
        mode_idx = next((i for i, (_, m) in enumerate(SITUATION_MODES) if m == saved_mode), 0)
        self._mode_row.set_selected(mode_idx)
        self._mode_row.connect("notify::selected", self._on_mode_changed)

        return [self._mode_row]

    def _on_mode_changed(self, row, _pspec):
        idx = row.get_selected()
        if 0 <= idx < len(SITUATION_MODES):
            _, mode_val = SITUATION_MODES[idx]
            settings = self.get_settings()
            settings["mode"] = mode_val
            self.set_settings(settings)
            self.update_display()

    def update_display(self):
        self._ensure_media_control()

        my_coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team_id, _ = self.plugin_base.sports_service.get_nearest_hub_target(my_coords)

        state = self.plugin_base.sports_service.get_game_state(hub_league, hub_team_id)
        summary = self.plugin_base.sports_service.get_game_summary(hub_league, hub_team_id)

        settings = self.get_settings()
        mode = settings.get("mode", "auto")

        img = Image.new("RGBA", (100, 100), (22, 24, 30, 255))
        draw = ImageDraw.Draw(img)

        font_hdr = get_bundled_font(10)
        font_main = get_bundled_font(13)
        font_sub = get_bundled_font(10)

        if mode == "venue_tv":
            # Header
            draw.rectangle([(0, 0), (100, 24)], fill=(35, 42, 54, 255))
            draw.line([(0, 24), (100, 24)], fill=(50, 60, 80, 255), width=1)
            draw.text((50, 12), "VENUE / TV", fill=(180, 195, 220, 255), anchor="mm", font=font_hdr)

            # Venue name
            v_name = summary.venue_name if summary.venue_name else "Stadium"
            draw.text((50, 46), v_name[:14], fill=(255, 255, 255, 255), anchor="mm", font=font_main)

            # Footer: TV & Weather
            draw.rectangle([(0, 76), (100, 100)], fill=(16, 18, 22, 255))
            draw.line([(0, 76), (100, 76)], fill=(45, 50, 60, 255), width=1)
            tv_str = summary.broadcast_channel if summary.broadcast_channel else (summary.weather_text[:14] if summary.weather_text else state.league_key)
            draw.text((50, 88), tv_str[:14], fill=(160, 210, 255, 255), anchor="mm", font=font_sub)

        elif mode == "ball_spot":
            # Header
            draw.rectangle([(0, 0), (100, 24)], fill=(180, 70, 20, 255) if "RED ZONE" in state.down_distance else (45, 50, 65, 255))
            draw.line([(0, 24), (100, 24)], fill=(255, 255, 255, 40), width=1)
            draw.text((50, 12), "BALL ON / BASES", fill=(255, 255, 255, 255), anchor="mm", font=font_hdr)

            # Main
            spot_text = state.down_distance if state.down_distance else ("Inning Radar" if state.league_key == "MLB" else "Midfield")
            draw.text((50, 48), spot_text[:12], fill=(255, 255, 255, 255), anchor="mm", font=font_main)

            # Footer
            draw.rectangle([(0, 76), (100, 100)], fill=(16, 18, 22, 255))
            draw.line([(0, 76), (100, 76)], fill=(45, 50, 60, 255), width=1)
            draw.text((50, 88), "RED ZONE" if "red" in state.down_distance.lower() else "Live Radar", fill=(255, 100, 100, 255) if "red" in state.down_distance.lower() else (160, 170, 190, 255), anchor="mm", font=font_sub)

        elif mode == "drive_pp":
            # Special Teams / Power Play / Drive Summary
            is_pp = ("5-on-4" in state.status_detail or "PP" in state.status_detail)
            hdr_bg = (180, 30, 30, 255) if is_pp else (35, 42, 54, 255)
            draw.rectangle([(0, 0), (100, 24)], fill=hdr_bg)
            draw.line([(0, 24), (100, 24)], fill=(255, 255, 255, 40), width=1)
            draw.text((50, 12), "POWER PLAY" if is_pp else "DRIVE INFO", fill=(255, 255, 255, 255), anchor="mm", font=font_hdr)

            draw.text((50, 48), state.clock if state.clock else state.period_text, fill=(255, 215, 60, 255), anchor="mm", font=font_main)

            draw.rectangle([(0, 76), (100, 100)], fill=(16, 18, 22, 255))
            draw.line([(0, 76), (100, 76)], fill=(45, 50, 60, 255), width=1)
            draw.text((50, 88), state.status_detail[:14], fill=(160, 170, 190, 255), anchor="mm", font=font_sub)

        else:
            # Default / Down & Distance
            draw.rectangle([(0, 0), (100, 24)], fill=(35, 42, 54, 255))
            draw.line([(0, 24), (100, 24)], fill=(50, 60, 80, 255), width=1)
            draw.text((50, 12), "SITUATION", fill=(180, 195, 220, 255), anchor="mm", font=font_hdr)

            sit_str = state.down_distance if state.down_distance else (state.clock if state.clock else state.status_detail)
            draw.text((50, 48), sit_str[:12], fill=(255, 255, 255, 255), anchor="mm", font=font_main)

            draw.rectangle([(0, 76), (100, 100)], fill=(16, 18, 22, 255))
            draw.line([(0, 76), (100, 76)], fill=(45, 50, 60, 255), width=1)
            draw.text((50, 88), state.period_text[:14] if state.period_text else "Active", fill=(160, 170, 190, 255), anchor="mm", font=font_sub)

        draw.rectangle([(0, 0), (99, 99)], outline=(50, 55, 68, 255), width=1)
        self.set_media(image=img)
