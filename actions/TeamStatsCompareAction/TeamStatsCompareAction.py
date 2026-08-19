"""
DeckSports TeamStatsCompareAction
Displays head-to-head metric comparison cards (Total Yards, 3rd Downs, Turnovers, Standings, etc.).
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
    from ...backend.SportsService import GameState, GameSummary
except (ImportError, ValueError):
    from backend.SportsService import GameState, GameSummary

COMPARE_METRICS = [
    ("Primary Metric (Total Yards / FG% / Hits)", 0),
    ("Secondary Metric (3rd Down% / 3PT% / SOG)", 1),
    ("Turnovers / Fouls / Penalty Minutes", 2),
    ("Time of Possession / Formations", 3),
    ("League Standings / Division Race", 4),
    ("Next Upcoming Match", 5),
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

class TeamStatsCompareAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._metric_row: Adw.ComboRow | None = None

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
        my_coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team, _ = self.plugin_base.sports_service.get_nearest_hub_target(my_coords)
        if hub_league and hub_team:
            self.plugin_base.sports_service.fetch_game_summary(hub_league, hub_team, force=True)

    def get_config_rows(self) -> list:
        metric_model = Gtk.StringList()
        for label, _ in COMPARE_METRICS:
            metric_model.append(label)

        self._metric_row = Adw.ComboRow(
            title="Comparison Metric",
            subtitle="Select the statistic or standing to display",
            model=metric_model
        )

        settings = self.get_settings()
        saved_idx = settings.get("metric_idx", 0)
        self._metric_row.set_selected(saved_idx)
        self._metric_row.connect("notify::selected", self._on_metric_changed)

        return [self._metric_row]

    def _on_metric_changed(self, row, _pspec):
        idx = row.get_selected()
        settings = self.get_settings()
        settings["metric_idx"] = idx
        self.set_settings(settings)
        self.update_display()

    def update_display(self):
        if not self.get_is_present():
            return
        self._ensure_media_control()

        my_coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team_id, _ = self.plugin_base.sports_service.get_nearest_hub_target(my_coords)

        state = self.plugin_base.sports_service.get_game_state(hub_league, hub_team_id)
        summary = self.plugin_base.sports_service.get_game_summary(hub_league, hub_team_id)

        settings = self.get_settings()
        metric_idx = settings.get("metric_idx", 0)

        img = Image.new("RGBA", (100, 100), (22, 24, 30, 255))
        draw = ImageDraw.Draw(img)

        font_hdr = get_bundled_font(10)
        font_main = get_bundled_font(14)
        font_sub = get_bundled_font(10)

        if metric_idx == 4:
            # Standings / Division
            draw.rectangle([(0, 0), (100, 24)], fill=(35, 42, 54, 255))
            draw.line([(0, 24), (100, 24)], fill=(50, 60, 80, 255), width=1)
            draw.text((50, 12), "STANDINGS", fill=(180, 195, 220, 255), anchor="mm", font=font_hdr)

            draw.text((50, 48), state.away_team.record if state.away_team.record else "Division", fill=(255, 210, 60, 255), anchor="mm", font=font_main)

            draw.rectangle([(0, 76), (100, 100)], fill=(16, 18, 22, 255))
            draw.line([(0, 76), (100, 76)], fill=(45, 50, 60, 255), width=1)
            draw.text((50, 88), state.home_team.record if state.home_team.record else "League Table", fill=(160, 170, 190, 255), anchor="mm", font=font_sub)

        elif metric_idx == 5:
            # Next Match
            draw.rectangle([(0, 0), (100, 24)], fill=(35, 42, 54, 255))
            draw.line([(0, 24), (100, 24)], fill=(50, 60, 80, 255), width=1)
            draw.text((50, 12), "NEXT MATCH", fill=(180, 195, 220, 255), anchor="mm", font=font_hdr)

            nxt_dt = state.next_game_date if state.next_game_date else "Upcoming"
            draw.text((50, 48), nxt_dt[:12], fill=(255, 255, 255, 255), anchor="mm", font=font_main)

            draw.rectangle([(0, 76), (100, 100)], fill=(16, 18, 22, 255))
            draw.line([(0, 76), (100, 76)], fill=(45, 50, 60, 255), width=1)
            nxt_tm = state.next_game_time if state.next_game_time else "Schedule"
            draw.text((50, 88), nxt_tm[:12], fill=(255, 210, 60, 255), anchor="mm", font=font_sub)

        else:
            # Stats Comparison from summary
            stat = summary.team_stats[metric_idx] if len(summary.team_stats) > metric_idx else None
            lbl = stat.label if stat else "TOTAL YDS"

            draw.rectangle([(0, 0), (100, 24)], fill=(35, 42, 54, 255))
            draw.line([(0, 24), (100, 24)], fill=(50, 60, 80, 255), width=1)
            draw.text((50, 12), lbl[:14].upper(), fill=(180, 195, 220, 255), anchor="mm", font=font_hdr)

            if stat:
                val_str = f"{stat.away_val} - {stat.home_val}"
            else:
                val_str = f"{state.away_team.score} - {state.home_team.score}"
            draw.text((50, 48), val_str[:12], fill=(255, 255, 255, 255), anchor="mm", font=font_main)

            draw.rectangle([(0, 76), (100, 100)], fill=(16, 18, 22, 255))
            draw.line([(0, 76), (100, 76)], fill=(45, 50, 60, 255), width=1)
            draw.text((50, 88), f"{state.away_team.abbreviation} vs {state.home_team.abbreviation}", fill=(160, 170, 190, 255), anchor="mm", font=font_sub)

        draw.rectangle([(0, 0), (99, 99)], outline=(50, 55, 68, 255), width=1)
        self.set_media(image=img)
