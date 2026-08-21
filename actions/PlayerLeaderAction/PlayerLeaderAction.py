"""
DeckSports PlayerLeaderAction
Displays category leader card with circular athlete headshots, names, and live performance metrics.
"""

import os
import time
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

def format_fitted_text(text: str, max_width: int = 90, max_size: int = 12, min_size: int = 8) -> tuple[str, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
    """Returns fitted text and font size that fits cleanly within max_width pixels without overflowing."""
    if not text:
        return "", get_bundled_font(max_size)

    for sz in range(max_size, min_size - 1, -1):
        f = get_bundled_font(sz)
        try:
            bbox = f.getbbox(text)
            if (bbox[2] - bbox[0]) <= max_width:
                return text, f
        except Exception:
            pass

    min_f = get_bundled_font(min_size)
    trimmed = text
    while len(trimmed) > 3:
        trimmed = trimmed[:-1]
        candidate = trimmed + "…"
        try:
            bbox = min_f.getbbox(candidate)
            if (bbox[2] - bbox[0]) <= max_width:
                return candidate, min_f
        except Exception:
            pass

    return text[:8], min_f

class PlayerLeaderAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._side_row: Adw.ComboRow | None = None
        self._cat_row: Adw.ComboRow | None = None
        self._cycle_timer: int | None = None
        self._manual_phase_override: int | None = None
        self._last_manual_toggle: float = 0.0

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
        my_coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team, _ = self.plugin_base.sports_service.get_nearest_hub_target(my_coords)
        if hub_league and hub_team:
            self.plugin_base.sports_service.fetch_game_summary(hub_league, hub_team, force=False)
        
        # Periodic 3.5-second animation cycle timer
        if self._cycle_timer is None:
            self._cycle_timer = GLib.timeout_add_seconds(3, self._on_cycle_timer)
        GLib.idle_add(self.update_display)

    def on_remove(self):
        if self._cycle_timer:
            try:
                GLib.source_remove(self._cycle_timer)
            except Exception:
                pass
            self._cycle_timer = None
        self.plugin_base.sports_service.remove_listener(self.on_game_state_updated)

    def _on_cycle_timer(self):
        if not self.get_is_present():
            return False
        self.update_display()
        return True

    def on_game_state_updated(self, league_key: str, team_id: str, state: GameState):
        GLib.idle_add(self.update_display)

    def on_key_down(self):
        # Interactive On-Tap Toggle: immediately flip between Portrait and Stat Breakdown
        now = time.time()
        cur_phase = int(now / 3.5) % 2 if self._manual_phase_override is None else self._manual_phase_override
        self._manual_phase_override = 1 - cur_phase
        self._last_manual_toggle = now

        my_coords = getattr(self.input_ident, "coords", None)
        hub_league, hub_team, _ = self.plugin_base.sports_service.get_nearest_hub_target(my_coords)
        if hub_league and hub_team:
            self.plugin_base.sports_service.fetch_game_summary(hub_league, hub_team, force=True)
        self.update_display()

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

        # Determine Active Phase (Phase 0 = Hero Headshot Portrait, Phase 1 = Live Stat Breakdown)
        now = time.time()
        if self._manual_phase_override is not None and (now - self._last_manual_toggle) < 6.0:
            phase = self._manual_phase_override
        else:
            self._manual_phase_override = None
            phase = int(now / 3.5) % 2

        img = Image.new("RGBA", (100, 100), (22, 24, 30, 255))
        draw = ImageDraw.Draw(img)

        header_color = team.color if team.color else (45, 45, 45, 255)
        draw.rectangle([(0, 0), (100, 24)], fill=header_color)
        draw.line([(0, 24), (100, 24)], fill=(255, 255, 255, 45), width=1)

        font_hdr = get_bundled_font(10)

        if phase == 0:
            # -----------------------------------------------------------------
            # PHASE 0: Hero Athlete Headshot Portrait View (Large 52x52px Avatar)
            # -----------------------------------------------------------------
            cat_title = leader.category.upper() if leader else "LEADER"
            hdr_text = f"{team.abbreviation} {cat_title}"[:15]
            draw.text((50, 12), hdr_text, fill=(255, 255, 255, 255), anchor="mm", font=font_hdr)

            # Circular Headshot Framing
            cx, cy = 50, 50
            draw.ellipse([(cx - 27, cy - 26), (cx + 27, cy + 26)], fill=(32, 38, 50, 255), outline=(75, 88, 115, 255), width=2)

            if leader and leader.headshot_url:
                hs = self.plugin_base.sports_service.get_headshot(leader.headshot_url, max_size=(52, 52))
                if hs:
                    img.alpha_composite(hs, (cx - hs.width // 2, cy - hs.height // 2))
            elif team.logo_url:
                mini_logo = self.plugin_base.sports_service.get_image(team.logo_url, max_size=(46, 46))
                if mini_logo:
                    img.alpha_composite(mini_logo, (cx - mini_logo.width // 2, cy - mini_logo.height // 2))

            # Jersey number badge overlay
            if leader and leader.jersey:
                badge_x = cx + 14
                badge_y = cy + 12
                draw.ellipse([(badge_x - 8, badge_y - 8), (badge_x + 8, badge_y + 8)], fill=(255, 215, 0, 255), outline=(20, 24, 30, 255), width=1)
                font_j = get_bundled_font(9)
                draw.text((badge_x, badge_y), f"{leader.jersey}", fill=(0, 0, 0, 255), anchor="mm", font=font_j)

            # Footer: Full Athlete Name
            draw.rectangle([(0, 76), (100, 100)], fill=(16, 18, 22, 255))
            draw.line([(0, 76), (100, 76)], fill=(45, 50, 60, 255), width=1)
            p_name = leader.name.upper() if leader else team.short_name.upper()
            name_disp, font_name = format_fitted_text(p_name, max_width=92, max_size=10, min_size=8)
            draw.text((50, 88), name_disp, fill=(255, 255, 255, 255), anchor="mm", font=font_name)

        else:
            # -----------------------------------------------------------------
            # PHASE 1: Live Performance Stat Breakdown View (Bold Key Numbers)
            # -----------------------------------------------------------------
            if leader and leader.jersey:
                hdr_text = f"{leader.short_name} #{leader.jersey}"
            elif leader:
                hdr_text = leader.short_name
            else:
                hdr_text = f"{team.abbreviation} STATS"
            draw.text((50, 12), hdr_text[:16], fill=(255, 255, 255, 255), anchor="mm", font=font_hdr)

            # Center: Bold Primary Stat
            stat_text = leader.display_stat if (leader and leader.display_stat) else team.record
            parts = [p.strip() for p in stat_text.replace(",", " ").split() if p.strip()]
            
            if parts:
                main_val = parts[0] + (" " + parts[1] if len(parts) > 1 and not parts[1].isdigit() else "")
                sub_val = " ".join(parts[1:]) if len(parts) > 1 and parts[1].isdigit() else (" ".join(parts[2:]) if len(parts) > 2 else (leader.category.upper() if leader else "RECORD"))
            else:
                main_val = stat_text
                sub_val = leader.category.upper() if leader else ""

            font_main = get_bundled_font(16 if len(main_val) <= 8 else 13)
            font_sub = get_bundled_font(11)

            draw.text((50, 42), main_val[:12], fill=(255, 220, 60, 255), anchor="mm", font=font_main)
            draw.text((50, 60), sub_val[:14], fill=(160, 210, 255, 255), anchor="mm", font=font_sub)

            # Footer: Full Stat Line
            draw.rectangle([(0, 76), (100, 100)], fill=(16, 18, 22, 255))
            draw.line([(0, 76), (100, 76)], fill=(45, 50, 60, 255), width=1)
            stat_disp, font_stat = format_fitted_text(stat_text, max_width=92, max_size=10, min_size=8)
            draw.text((50, 88), stat_disp, fill=(180, 205, 235, 255), anchor="mm", font=font_stat)

        draw.rectangle([(0, 0), (99, 99)], outline=(50, 55, 68, 255), width=1)
        self.set_media(image=img)
