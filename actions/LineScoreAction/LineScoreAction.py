"""
DeckSports LineScoreAction
Displays quarter-by-quarter / period / inning line scores for Away and Home teams.
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

SLOT_OPTIONS = [
    ("Away Full Line Score (e.g. 7 3 0 7 = 17)", "away_full"),
    ("Home Full Line Score (e.g. 3 7 7 7 = 24)", "home_full"),
    ("Quarter / Period 1 (Q1)", "p1"),
    ("Quarter / Period 2 (Q2)", "p2"),
    ("Quarter / Period 3 (Q3)", "p3"),
    ("Quarter / Period 4 (Q4)", "p4"),
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

class LineScoreAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._slot_row: Adw.ComboRow | None = None

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
        slot_model = Gtk.StringList()
        for label, _ in SLOT_OPTIONS:
            slot_model.append(label)

        self._slot_row = Adw.ComboRow(
            title="Line Score Display Slot",
            subtitle="Choose which period or team line score to render",
            model=slot_model
        )

        settings = self.get_settings()
        saved_slot = settings.get("slot", "away_full")
        slot_idx = next((i for i, (_, s) in enumerate(SLOT_OPTIONS) if s == saved_slot), 0)
        self._slot_row.set_selected(slot_idx)
        self._slot_row.connect("notify::selected", self._on_slot_changed)

        return [self._slot_row]

    def _on_slot_changed(self, row, _pspec):
        idx = row.get_selected()
        if 0 <= idx < len(SLOT_OPTIONS):
            _, slot_val = SLOT_OPTIONS[idx]
            settings = self.get_settings()
            settings["slot"] = slot_val
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
        slot = settings.get("slot", "away_full")

        img = Image.new("RGBA", (100, 100), (22, 24, 30, 255))
        draw = ImageDraw.Draw(img)

        if slot == "away_full":
            # Header with away team color
            header_color = state.away_team.color if state.away_team.color else (40, 60, 120, 255)
            draw.rectangle([(0, 0), (100, 24)], fill=header_color)
            draw.line([(0, 24), (100, 24)], fill=(255, 255, 255, 40), width=1)

            font_hdr = get_bundled_font(11)
            draw.text((50, 12), f"{state.away_team.abbreviation} LINE", fill=(255, 255, 255, 255), anchor="mm", font=font_hdr)

            # Linescores
            lines = summary.away_linescores if summary.away_linescores else []
            lines_str = " ".join(lines[:5]) if lines else (f"R:{state.away_team.score}" if state.league_key == "MLB" else "—")
            font_lines = get_bundled_font(15 if len(lines_str) <= 8 else 12)
            draw.text((50, 48), lines_str, fill=(255, 255, 255, 255), anchor="mm", font=font_lines)

            # Footer: Total
            draw.rectangle([(0, 78), (100, 100)], fill=(16, 18, 22, 255))
            draw.line([(0, 78), (100, 78)], fill=(45, 50, 60, 255), width=1)
            font_foot = get_bundled_font(10)
            draw.text((50, 89), f"Q1 Q2 Q3 Q4" if len(lines) >= 4 else f"Total: {state.away_team.score}", fill=(160, 170, 190, 255), anchor="mm", font=font_foot)

        elif slot == "home_full":
            header_color = state.home_team.color if state.home_team.color else (120, 40, 40, 255)
            draw.rectangle([(0, 0), (100, 24)], fill=header_color)
            draw.line([(0, 24), (100, 24)], fill=(255, 255, 255, 40), width=1)

            font_hdr = get_bundled_font(11)
            draw.text((50, 12), f"{state.home_team.abbreviation} LINE", fill=(255, 255, 255, 255), anchor="mm", font=font_hdr)

            lines = summary.home_linescores if summary.home_linescores else []
            lines_str = " ".join(lines[:5]) if lines else (f"R:{state.home_team.score}" if state.league_key == "MLB" else "—")
            font_lines = get_bundled_font(15 if len(lines_str) <= 8 else 12)
            draw.text((50, 48), lines_str, fill=(255, 255, 255, 255), anchor="mm", font=font_lines)

            draw.rectangle([(0, 78), (100, 100)], fill=(16, 18, 22, 255))
            draw.line([(0, 78), (100, 78)], fill=(45, 50, 60, 255), width=1)
            font_foot = get_bundled_font(10)
            draw.text((50, 89), f"Q1 Q2 Q3 Q4" if len(lines) >= 4 else f"Total: {state.home_team.score}", fill=(160, 170, 190, 255), anchor="mm", font=font_foot)

        else:
            # Individual Periods (p1, p2, p3, p4)
            p_idx = 0
            if slot == "p2":
                p_idx = 1
            elif slot == "p3":
                p_idx = 2
            elif slot == "p4":
                p_idx = 3

            draw.rectangle([(0, 0), (100, 24)], fill=(32, 36, 46, 255))
            draw.line([(0, 24), (100, 24)], fill=(50, 60, 75, 255), width=1)

            font_hdr = get_bundled_font(11)
            draw.text((50, 12), f"DRIVES • Q{p_idx + 1}" if state.league_key in ("NFL", "UFL", "NBA") else f"PERIOD {p_idx + 1}", fill=(180, 195, 215, 255), anchor="mm", font=font_hdr)

            a_sc = summary.away_linescores[p_idx] if len(summary.away_linescores) > p_idx else "0"
            h_sc = summary.home_linescores[p_idx] if len(summary.home_linescores) > p_idx else "0"

            font_main = get_bundled_font(13)
            match_str = f"{state.away_team.abbreviation} {a_sc} - {state.home_team.abbreviation} {h_sc}"
            draw.text((50, 48), match_str, fill=(255, 255, 255, 255), anchor="mm", font=font_main)

            draw.rectangle([(0, 78), (100, 100)], fill=(16, 18, 22, 255))
            draw.line([(0, 78), (100, 78)], fill=(45, 50, 60, 255), width=1)
            font_foot = get_bundled_font(10)
            draw.text((50, 89), f"{state.status_detail[:14]}", fill=(150, 160, 180, 255), anchor="mm", font=font_foot)

        draw.rectangle([(0, 0), (99, 99)], outline=(50, 55, 68, 255), width=1)
        self.set_media(image=img)
