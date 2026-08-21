"""
DeckSports CelebrationManager
Full-deck synchronized score celebration animation engine with sport-specific visual themes.
Renders full-matrix visual celebration sequences across Stream Deck XL (8x4) and MK.2 (5x3) keypads.
"""

import os
import time
import math
import threading
import logging
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
from gi.repository import GLib
import globals as gl
from .Leagues import LEAGUES

log = logging.getLogger("DeckSports")

@lru_cache(maxsize=32)
def get_cached_font(size: int = 24) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    plugin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    bundled_font = os.path.join(plugin_dir, "assets", "fonts", "ScoreFont-Bold.ttf")
    if os.path.exists(bundled_font):
        try:
            return ImageFont.truetype(bundled_font, size)
        except Exception:
            pass
    return ImageFont.load_default()


def get_celebration_text(league_key: str, sport_slug: str, score_delta: int = 0, event_detail: str = "") -> str:
    """Determine dynamic celebration text based on sport, league rules, and scoring magnitude."""
    sport = sport_slug.lower() if sport_slug else ""
    if not sport:
        if league_key in ("NFL", "UFL", "NCAA_FB"):
            sport = "football"
        elif league_key in ("NBA", "WNBA", "NCAA_MBB", "NCAA_BK"):
            sport = "basketball"
        elif league_key in ("MLB",):
            sport = "baseball"
        elif league_key in ("NHL",):
            sport = "hockey"
        elif league_key in ("MLS",):
            sport = "soccer"

    detail_lower = event_detail.lower()

    if sport == "football":
        if league_key == "UFL":
            # UFL Specific Scoring Rules
            if score_delta == 4 or "4-pt" in detail_lower or "60" in detail_lower or "super kick" in detail_lower:
                return "4-PT SUPER KICK!"
            elif score_delta == 3:
                return "3-PT CONVERSION!" if ("conversion" in detail_lower or "conv" in detail_lower) else "FIELD GOAL!"
            elif score_delta == 2:
                return "2-PT CONVERSION!"
            elif score_delta == 1:
                return "1-PT CONVERSION!"
            elif score_delta >= 6:
                return "TOUCHDOWN!"
            return "TOUCHDOWN!"
        else:
            # NFL & College Football
            if score_delta >= 6:
                return "TOUCHDOWN!"
            elif score_delta == 3:
                return "FIELD GOAL!"
            elif score_delta == 2:
                return "2-PT CONVERSION!" if ("conversion" in detail_lower or "conv" in detail_lower) else "SAFETY!"
            elif score_delta == 1:
                return "EXTRA POINT GOOD!"
            return "TOUCHDOWN!"

    elif sport == "basketball":
        if score_delta >= 3:
            return "3-POINTER!"
        elif score_delta == 1:
            return "FREE THROW!"
        elif score_delta == 2:
            return "SLAM DUNK!" if ("dunk" in detail_lower or "alley" in detail_lower) else "BASKET!"
        return "SLAM DUNK!"

    elif sport == "baseball":
        if score_delta >= 4 or "grand slam" in detail_lower:
            return "GRAND SLAM!"
        elif score_delta in (2, 3) or "home run" in detail_lower:
            return "HOME RUN!"
        elif score_delta == 1:
            return "RUN SCORED!"
        return "HOME RUN!"

    elif sport == "hockey":
        if "ppg" in detail_lower or "power play" in detail_lower or "5-on-4" in detail_lower:
            return "POWER PLAY GOAL!"
        elif "shg" in detail_lower or "shorthanded" in detail_lower:
            return "SHORTHANDED GOAL!"
        return "GOAL!"

    elif sport == "soccer":
        if "penalty" in detail_lower or "pk" in detail_lower or "shootout" in detail_lower:
            return "PENALTY GOAL!"
        return "GOAL!"

    return "SCORE!"


class CelebrationManager:
    def __init__(self, sports_service):
        self.sports_service = sports_service
        self.is_animating = False
        self._cancel_requested = False
        self._lock = threading.Lock()

    def cancel(self):
        with self._lock:
            self._cancel_requested = True

    def trigger(
        self,
        league_key: str,
        team_name: str,
        team_abbrev: str,
        primary_color: tuple,
        alt_color: tuple,
        celebration_text: str = "",
        score_delta: int = 0,
        event_detail: str = "",
        force_preview: bool = False
    ):
        with self._lock:
            if self.is_animating:
                return
            self.is_animating = True
            self._cancel_requested = False

        threading.Thread(
            target=self._run_celebration_worker,
            args=(league_key, team_name, team_abbrev, primary_color, alt_color, celebration_text, score_delta, event_detail, False, "", force_preview),
            daemon=True
        ).start()

    def trigger_victory(
        self,
        league_key: str,
        team_name: str,
        team_abbrev: str,
        primary_color: tuple,
        alt_color: tuple,
        my_score: str = "",
        opp_abbrev: str = "",
        opp_score: str = "",
        force_preview: bool = False
    ):
        """Triggers a 4.0-second full-deck celebratory victory animation with confetti rain and fireworks."""
        with self._lock:
            if self.is_animating:
                return
            self.is_animating = True
            self._cancel_requested = False

        subtitle = f"FINAL: {team_abbrev} {my_score} - {opp_abbrev} {opp_score}" if (my_score and opp_score) else f"{team_name.upper()} WINS!"
        threading.Thread(
            target=self._run_celebration_worker,
            args=(league_key, team_name, team_abbrev, primary_color, alt_color, "VICTORY!", 0, "", True, subtitle, force_preview),
            daemon=True
        ).start()

    def trigger_test_preview(self, anim_type: str):
        """Plays any of the sport-specific celebration animations as a forced live preview across connected hardware."""
        samples = {
            # NFL (American Football)
            "nfl_td": ("NFL", "Las Vegas Raiders", "LV", (0, 0, 0, 255), (165, 172, 175, 255), "TOUCHDOWN!", 6, "touchdown", False, ""),
            "nfl_fg": ("NFL", "Las Vegas Raiders", "LV", (0, 0, 0, 255), (165, 172, 175, 255), "FIELD GOAL! (+3 PTS)", 3, "field goal", False, ""),
            "nfl_pat": ("NFL", "Las Vegas Raiders", "LV", (0, 0, 0, 255), (165, 172, 175, 255), "EXTRA POINT GOOD!", 1, "extra point", False, ""),
            "nfl_2pt": ("NFL", "Las Vegas Raiders", "LV", (0, 0, 0, 255), (165, 172, 175, 255), "2-PT CONVERSION!", 2, "2-pt conversion", False, ""),
            "nfl_safety": ("NFL", "Las Vegas Raiders", "LV", (0, 0, 0, 255), (165, 172, 175, 255), "SAFETY! (+2 PTS)", 2, "safety", False, ""),

            # UFL (Spring Football - Official Rules)
            "ufl_td": ("UFL", "DC Defenders", "DC", (200, 16, 46, 255), (255, 255, 255, 255), "TOUCHDOWN!", 6, "touchdown", False, ""),
            "ufl_4pt": ("UFL", "DC Defenders", "DC", (200, 16, 46, 255), (255, 255, 255, 255), "4-PT SUPER KICK!", 4, "4-pt field goal", False, "60+ YD MONSTER FIELD GOAL! (+4 PTS)"),
            "ufl_fg": ("UFL", "DC Defenders", "DC", (200, 16, 46, 255), (255, 255, 255, 255), "FIELD GOAL! (+3 PTS)", 3, "field goal", False, ""),
            "ufl_3pt": ("UFL", "DC Defenders", "DC", (200, 16, 46, 255), (255, 255, 255, 255), "3-PT CONVERSION!", 3, "3-pt conversion", False, "8-YD SCRIMMAGE / 9-PT SUPER DRIVE"),
            "ufl_2pt": ("UFL", "DC Defenders", "DC", (200, 16, 46, 255), (255, 255, 255, 255), "2-PT CONVERSION!", 2, "2-pt conversion", False, "2-YD SCRIMMAGE CONVERSION"),
            "ufl_1pt": ("UFL", "DC Defenders", "DC", (200, 16, 46, 255), (255, 255, 255, 255), "1-PT CONVERSION!", 1, "1-pt conversion", False, "33-YD PAT FIELD GOAL"),
            "ufl_ot": ("UFL", "DC Defenders", "DC", (200, 16, 46, 255), (255, 255, 255, 255), "OVERTIME CONVERSION GOOD!", 2, "overtime", False, "UFL OVERTIME SHOOTOUT"),
            "ufl_safety": ("UFL", "DC Defenders", "DC", (200, 16, 46, 255), (255, 255, 255, 255), "SAFETY! (+2 PTS)", 2, "safety", False, ""),

            # Basketball (NBA, WNBA, NCAA)
            "nba_dunk": ("NBA", "Los Angeles Lakers", "LAL", (85, 37, 130, 255), (253, 185, 39, 255), "SLAM DUNK!", 2, "dunk", False, ""),
            "nba_3pt": ("NBA", "Golden State Warriors", "GSW", (29, 66, 138, 255), (255, 199, 44, 255), "3-POINTER FROM DOWNTOWN!", 3, "3-pointer", False, ""),
            "nba_buzzer": ("NBA", "Boston Celtics", "BOS", (0, 122, 51, 255), (255, 255, 255, 255), "BUZZER BEATER WINNER!", 3, "buzzer beater", False, ""),
            "nba_ft": ("NBA", "Los Angeles Lakers", "LAL", (85, 37, 130, 255), (253, 185, 39, 255), "FREE THROW!", 1, "free throw", False, ""),

            # MLB (Baseball)
            "mlb_grand_slam": ("MLB", "New York Yankees", "NYY", (12, 35, 64, 255), (255, 255, 255, 255), "GRAND SLAM!", 4, "grand slam", False, "4-RUN BASES LOADED HOME RUN"),
            "mlb_hr": ("MLB", "Los Angeles Dodgers", "LAD", (0, 90, 156, 255), (255, 255, 255, 255), "HOME RUN!", 1, "home run", False, ""),
            "mlb_walkoff": ("MLB", "Houston Astros", "HOU", (0, 45, 98, 255), (235, 110, 31, 255), "WALK-OFF WINNER!", 1, "walk-off", False, "GAME WINNING HIT"),
            "mlb_rbi": ("MLB", "Boston Red Sox", "BOS", (189, 48, 57, 255), (13, 43, 86, 255), "RUN SCORED!", 1, "rbi", False, ""),

            # NHL (Hockey)
            "nhl_goal": ("NHL", "Vegas Golden Knights", "VGK", (180, 151, 90, 255), (51, 63, 72, 255), "GOAL!", 1, "goal", False, ""),
            "nhl_ppg": ("NHL", "Edmonton Oilers", "EDM", (4, 30, 66, 255), (255, 79, 0, 255), "POWER PLAY GOAL! (PPG)", 1, "ppg", False, "5-ON-4 POWER PLAY ADVANTAGE"),
            "nhl_shg": ("NHL", "Boston Bruins", "BOS", (252, 181, 20, 255), (0, 0, 0, 255), "SHORT-HANDED GOAL! (SHG)", 1, "shg", False, "4-ON-5 PENALTY KILL BREAKAWAY"),
            "nhl_en": ("NHL", "New York Rangers", "NYR", (0, 56, 168, 255), (206, 17, 38, 255), "EMPTY NET GOAL! (EN)", 1, "empty net", False, ""),

            # Soccer (MLS, Premier League)
            "mls_goal": ("MLS", "Inter Miami CF", "MIA", (247, 181, 206, 255), (0, 0, 0, 255), "GOAL!", 1, "goal", False, ""),
            "mls_pk": ("MLS", "LA Galaxy", "LA", (0, 36, 93, 255), (255, 210, 0, 255), "PENALTY GOAL! (PK)", 1, "pk", False, "SPOT KICK CONVERSION"),
            "mls_shootout": ("MLS", "Seattle Sounders FC", "SEA", (0, 85, 149, 255), (93, 184, 45, 255), "SHOOTOUT GOAL!", 1, "shootout", False, "DECISIVE PENALTY SHOOTOUT"),

            # Post-Game Victory (All Sports)
            "victory_jumbotron": ("NFL", "Las Vegas Raiders", "LV", (0, 0, 0, 255), (165, 172, 175, 255), "VICTORY!", 0, "", True, "FINAL: LV 22 - HOU 20")
        }
        cfg = samples.get(anim_type, samples["nfl_td"])
        with self._lock:
            if self.is_animating:
                return
            self.is_animating = True
            self._cancel_requested = False

        threading.Thread(
            target=self._run_celebration_worker,
            args=(cfg[0], cfg[1], cfg[2], cfg[3], cfg[4], cfg[5], cfg[6], cfg[7], cfg[8], cfg[9], True),
            daemon=True
        ).start()

    def _run_celebration_worker(
        self,
        league_key: str,
        team_name: str,
        team_abbrev: str,
        primary_color: tuple,
        alt_color: tuple,
        celebration_text: str,
        score_delta: int,
        event_detail: str = "",
        is_victory: bool = False,
        custom_subtitle: str = "",
        force_preview: bool = False
    ):
        try:
            sport_slug = ""
            if league_key in LEAGUES:
                sport_slug = LEAGUES[league_key].sport_slug

            if not celebration_text:
                celebration_text = get_celebration_text(league_key, sport_slug, score_delta, event_detail)

            controller = None
            if hasattr(gl, "deck_manager") and getattr(gl.deck_manager, "deck_controller", None):
                controllers = gl.deck_manager.deck_controller
                if controllers:
                    controller = controllers[0]

            if not controller:
                return

            if not force_preview:
                # 1. Guard: Only play score celebration on Game Hub pages
                active_page = getattr(controller, "active_page", None)
                if not active_page:
                    return

                page_name = ""
                if hasattr(active_page, "get_name") and callable(active_page.get_name):
                    try:
                        page_name = active_page.get_name()
                    except Exception:
                        pass
                if not page_name:
                    page_name = str(getattr(active_page, "name", ""))
                json_path = str(getattr(active_page, "json_path", ""))

                is_game_hub = ("GameHub" in page_name) or ("GameHub" in json_path)
                if not is_game_hub:
                    # Never play animation on main profile or other pages
                    return

                # 2. Check Global Plugin Setting (Master toggle)
                global_enabled = True
                if hasattr(self, "plugin_base") and self.plugin_base:
                    global_enabled = self.plugin_base.get_settings().get("enable_celebrations", True)
                elif hasattr(self.sports_service, "plugin_base") and self.sports_service.plugin_base:
                    global_enabled = self.sports_service.plugin_base.get_settings().get("enable_celebrations", True)

                if not global_enabled:
                    return

                # 3. Check Per-Action Setting on active GameHubAction
                all_actions = active_page.get_all_actions()
                action_enabled = True
                for act in all_actions:
                    if act.__class__.__name__ == "GameHubAction":
                        settings = act.get_settings()
                        action_enabled = settings.get("enable_celebrations", True)
                        break

                if not action_enabled:
                    return

            cols, rows = 8, 4
            deck = getattr(controller, "deck", None)
            key_count = 32
            if deck and hasattr(deck, "key_count"):
                try:
                    key_count = deck.key_count()
                except Exception:
                    pass
            elif hasattr(controller, "inputs") and hasattr(controller.inputs, "__contains__"):
                from src.backend.DeckManagement.InputIdentifier import Input
                if Input.Key in controller.inputs:
                    key_count = len(controller.inputs[Input.Key])

            if key_count < 32:
                cols, rows = 5, 3

            canvas_w = cols * 100
            canvas_h = rows * 100

            total_frames = 60 if is_victory else 45
            fps = 15
            frame_duration = 1.0 / fps

            logo_img = None
            teams = self.sports_service.get_teams(league_key)
            my_team = next((t for t in teams if t.get("name") == team_name or t.get("abbreviation") == team_abbrev), None)
            if my_team and my_team.get("logo_url"):
                logo_img = self.sports_service.get_image(my_team["logo_url"], max_size=(180, 180))

            p_rgb = primary_color[:3] if len(primary_color) >= 3 else (0, 53, 148)
            s_rgb = alt_color[:3] if len(alt_color) >= 3 else (200, 205, 215)

            # Select background renderer based on sport and scoring event
            is_conversion = any(kw in celebration_text for kw in ("CONVERSION", "CONV", "EXTRA POINT", "PAT", "SHOOTOUT"))
            is_fg = (
                not is_victory
                and not is_conversion
                and sport_slug == "football"
                and ("FIELD GOAL" in celebration_text or "SUPER KICK" in celebration_text or (score_delta == 3 and not is_conversion))
            )
            is_ufl_mega = (
                not is_victory
                and not is_conversion
                and league_key == "UFL"
                and ("SUPER KICK" in celebration_text or ("4-PT" in celebration_text and not is_conversion) or score_delta == 4)
            )

            sport_renderer = self._draw_default_background
            if is_victory:
                sport_renderer = self._draw_victory_background
            elif sport_slug == "football" and not is_fg:
                sport_renderer = self._draw_football_background
            elif sport_slug == "basketball":
                sport_renderer = self._draw_basketball_background
            elif sport_slug == "baseball":
                sport_renderer = self._draw_baseball_background
            elif sport_slug == "hockey":
                sport_renderer = self._draw_hockey_background
            elif sport_slug == "soccer":
                sport_renderer = self._draw_soccer_background

            # Check if direct hardware USB pushing is available
            pil_helper = None
            try:
                from StreamDeck.ImageHelpers import PILHelper
                pil_helper = PILHelper
            except Exception:
                pass

            direct_hardware = bool(deck and hasattr(deck, "set_key_image") and pil_helper)
            rotation = deck.get_rotation() if (deck and hasattr(deck, "get_rotation")) else 0

            # Monotonic high-precision delta frame scheduler
            target_time = time.perf_counter()

            for frame_idx in range(total_frames):
                if self._cancel_requested:
                    break

                if not force_preview:
                    # Abort if active page has changed away from GameHub
                    current_page = getattr(controller, "active_page", None)
                    if not current_page or ("GameHub" not in str(getattr(current_page, "name", "")) and "GameHub" not in str(getattr(current_page, "json_path", ""))):
                        break

                frame_canvas = Image.new("RGBA", (canvas_w, canvas_h), (16, 18, 24, 255))
                draw = ImageDraw.Draw(frame_canvas)
                progress = frame_idx / total_frames

                # Draw sport-specific background
                if is_fg:
                    self._draw_field_goal_background(
                        draw, canvas_w, canvas_h, p_rgb, s_rgb, frame_idx, progress, cols, rows,
                        logo_img=logo_img, is_ufl_mega=is_ufl_mega, frame_canvas=frame_canvas
                    )
                else:
                    sport_renderer(draw, canvas_w, canvas_h, p_rgb, s_rgb, frame_idx, progress, cols, rows)

                # Center pulsing logo (suppressed during Field Goal so uprights remain clear)
                if logo_img and not is_fg:
                    scale_factor = 1.0 + 0.15 * math.sin(progress * math.pi * 4)
                    scaled_w = int(logo_img.width * scale_factor)
                    scaled_h = int(logo_img.height * scale_factor)
                    scaled_logo = logo_img.resize((scaled_w, scaled_h), Image.Resampling.BILINEAR)
                    lx = (canvas_w - scaled_w) // 2
                    ly = (canvas_h - scaled_h) // 2 - 20
                    frame_canvas.alpha_composite(scaled_logo, (lx, ly))

                # Celebration banner
                banner_y1 = int(canvas_h * 0.48)
                banner_y2 = int(canvas_h * 0.82)
                draw.rectangle([(0, banner_y1), (canvas_w, banner_y2)], fill=(12, 14, 18, 230))
                draw.line([(0, banner_y1), (canvas_w, banner_y1)], fill=(255, 215, 0, 255), width=3)
                draw.line([(0, banner_y2), (canvas_w, banner_y2)], fill=(255, 215, 0, 255), width=3)

                # Dual endcap team logos on banner for Field Goals
                if is_fg and logo_img:
                    badge_size = min(42, banner_y2 - banner_y1 - 10)
                    if badge_size > 10:
                        b_logo = logo_img.resize((badge_size, badge_size), Image.Resampling.BILINEAR)
                        left_badge_x = int(canvas_w * 0.08)
                        right_badge_x = canvas_w - int(canvas_w * 0.08) - badge_size
                        badge_y = (banner_y1 + banner_y2 - badge_size) // 2
                        frame_canvas.alpha_composite(b_logo, (left_badge_x, badge_y))
                        frame_canvas.alpha_composite(b_logo, (right_badge_x, badge_y))

                font_title = get_cached_font(52 if cols >= 8 else 36)
                font_sub = get_cached_font(26 if cols >= 8 else 18)

                # Title text with drop shadow and alternating bright strobe
                draw.text(
                    (canvas_w // 2 + 3, (banner_y1 + banner_y2) // 2 - 12 + 3),
                    celebration_text,
                    fill=(0, 0, 0, 255),
                    anchor="mm",
                    font=font_title
                )
                text_color = (255, 255, 255, 255) if (frame_idx % 2 == 0) else (255, 225, 50, 255)
                draw.text(
                    (canvas_w // 2, (banner_y1 + banner_y2) // 2 - 12),
                    celebration_text,
                    fill=text_color,
                    anchor="mm",
                    font=font_title
                )

                # Subtitle (Team Name or Victory Scoreline)
                sub_label = custom_subtitle if custom_subtitle else f"{team_name.upper()}"
                draw.text(
                    (canvas_w // 2, banner_y2 - 22),
                    sub_label,
                    fill=(200, 225, 255, 255),
                    anchor="mm",
                    font=font_sub
                )

                if direct_hardware:
                    # 1. Direct hardware native USB sweep (physical Stream Deck)
                    rgb_canvas = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
                    rgb_canvas.paste(frame_canvas, (0, 0), frame_canvas)
                    for ky in range(rows):
                        for kx in range(cols):
                            rgb_tile = rgb_canvas.crop((kx * 100, ky * 100, (kx + 1) * 100, (ky + 1) * 100))
                            if rotation:
                                rgb_tile = rgb_tile.rotate(rotation)
                            try:
                                native_img = pil_helper.to_native_key_format(deck, rgb_tile)
                                key_idx = ky * cols + kx
                                deck.set_key_image(key_idx, native_img)
                            except Exception:
                                pass

                    # 2. Desktop UI preview update via direct KeyGrid (pure software UI, zero USB contention)
                    tiles = {}
                    for ky in range(rows):
                        for kx in range(cols):
                            tiles[(kx, ky)] = frame_canvas.crop((kx * 100, ky * 100, (kx + 1) * 100, (ky + 1) * 100))

                    def _push_ui_preview(t_dict):
                        if not controller:
                            return
                        try:
                            deck_stack_child = controller.get_own_deck_stack_child()
                            if deck_stack_child and hasattr(deck_stack_child, "page_settings"):
                                deck_config = getattr(deck_stack_child.page_settings, "deck_config", None)
                                grid = getattr(deck_config, "grid", None) if deck_config else None
                                if grid and hasattr(grid, "buttons"):
                                    for (kx, ky), tile_img in t_dict.items():
                                        if kx < len(grid.buttons) and ky < len(grid.buttons[kx]):
                                            btn = grid.buttons[kx][ky]
                                            if btn and hasattr(btn, "set_image"):
                                                btn.set_image(tile_img)
                        except Exception:
                            pass

                    GLib.idle_add(_push_ui_preview, tiles)
                else:
                    # Fallback path for mock / virtual controllers
                    tiles = {}
                    for ky in range(rows):
                        for kx in range(cols):
                            tiles[(kx, ky)] = frame_canvas.crop((kx * 100, ky * 100, (kx + 1) * 100, (ky + 1) * 100))

                    def _push_tiles(t_dict):
                        active_page = getattr(controller, "active_page", None)
                        if active_page:
                            for act in active_page.get_all_actions():
                                coords = getattr(act.input_ident, "coords", None)
                                if coords and len(coords) >= 2:
                                    t = t_dict.get((coords[0], coords[1]))
                                    if t:
                                        act.set_media(image=t)

                    GLib.idle_add(_push_tiles, tiles)

                target_time += frame_duration
                sleep_delay = target_time - time.perf_counter()
                if sleep_delay > 0:
                    time.sleep(sleep_delay)

        except Exception as e:
            log.error(f"Error in score celebration animation: {e}")
        finally:
            with self._lock:
                self.is_animating = False
                self._cancel_requested = False
            GLib.idle_add(self._restore_deck_state, controller)

    def _restore_deck_state(self, controller):
        """Invalidates cached hardware image hashes and forces full-matrix scoreboard refresh via direct hardware push."""
        try:
            pil_helper = None
            try:
                from StreamDeck.ImageHelpers import PILHelper
                pil_helper = PILHelper
            except Exception:
                pass

            deck = getattr(controller, "deck", None) if controller else None
            rotation = deck.get_rotation() if (deck and hasattr(deck, "get_rotation")) else 0

            # 1. Update data models across all listeners
            self.sports_service.notify_all()

            # 2. Invoke update_display on every action on the active page to compute fresh Pillow images
            active_page = getattr(controller, "active_page", None) if controller else None
            if active_page and hasattr(active_page, "get_all_actions"):
                for act in active_page.get_all_actions():
                    if hasattr(act, "update_display") and callable(act.update_display):
                        try:
                            act.update_display()
                        except Exception:
                            pass

            # 3. Direct hardware sweep: push composed key images directly to physical Stream Deck USB
            if deck and hasattr(deck, "set_key_image") and pil_helper and controller and hasattr(controller, "inputs"):
                try:
                    from src.backend.DeckManagement.InputIdentifier import Input
                    key_inputs = controller.inputs.get(Input.Key, [])
                except Exception:
                    key_inputs = []
                    if hasattr(controller, "inputs"):
                        for t in controller.inputs:
                            if "key" in str(t).lower():
                                key_inputs.extend(controller.inputs[t])

                for key in key_inputs:
                    try:
                        if hasattr(key, "get_current_image"):
                            img = key.get_current_image()
                            if img:
                                rgb_img = Image.new("RGB", img.size, (0, 0, 0))
                                rgb_img.paste(img, (0, 0), img)
                                if rotation:
                                    rgb_img = rgb_img.rotate(rotation)
                                native_img = pil_helper.to_native_key_format(deck, rgb_img)
                                deck.set_key_image(key.index, native_img)
                    except Exception:
                        pass

            # 4. Clear cached image hashes on controller inputs so subsequent normal updates succeed
            if controller and hasattr(controller, "inputs"):
                for input_type in controller.inputs:
                    for inp in controller.inputs[input_type]:
                        if hasattr(inp, "_last_img_hash"):
                            inp._last_img_hash = None

            if controller and hasattr(controller, "update_all_inputs"):
                try:
                    controller.update_all_inputs()
                except Exception:
                    pass
        except Exception as e:
            log.error(f"Error restoring deck state after celebration: {e}")

    # -------------------------------------------------------------------------
    # Sport-Specific Background Renderers
    # -------------------------------------------------------------------------

    def _draw_victory_background(self, draw, canvas_w, canvas_h, p_rgb, s_rgb, frame_idx, progress, cols, rows):
        """Victory: Golden stadium atmosphere, animated multi-colored confetti shower, and starburst fireworks."""
        # 1. Team-tinted victory backdrop
        bg_r = min(255, max(0, int(p_rgb[0] * 0.25 + 15)))
        bg_g = min(255, max(0, int(p_rgb[1] * 0.25 + 15)))
        bg_b = min(255, max(0, int(p_rgb[2] * 0.25 + 25)))
        draw.rectangle([(0, 0), (canvas_w, canvas_h)], fill=(bg_r, bg_g, bg_b, 255))

        # 2. Golden Stadium Spotlight Beams
        for bx in (int(canvas_w * 0.15), int(canvas_w * 0.5), int(canvas_w * 0.85)):
            beam_tilt = int(math.sin(progress * math.pi * 4 + bx) * 40)
            draw.polygon([(bx - 30, 0), (bx + 30, 0), (bx + beam_tilt + 90, canvas_h), (bx + beam_tilt - 90, canvas_h)], fill=(255, 225, 120, 25))

        # 3. Multi-Color Confetti Rain (drifting downwards across full matrix)
        confetti_colors = [
            (p_rgb[0], p_rgb[1], p_rgb[2], 240),
            (s_rgb[0], s_rgb[1], s_rgb[2], 240),
            (255, 215, 0, 240),   # Gold
            (255, 255, 255, 240),  # White
            (255, 60, 60, 240)    # Bright Red
        ]
        confetti_count = 36
        for ci in range(confetti_count):
            seed_x = (ci * 37) % canvas_w
            speed = 1.2 + (ci % 5) * 0.3
            cx = (seed_x + int(math.sin(progress * math.pi * 6 + ci) * 20)) % canvas_w
            cy = int((frame_idx * 7 * speed + ci * 25)) % canvas_h
            cw = 6 + (ci % 4) * 2
            ch = 4 + (ci % 3) * 2
            c_color = confetti_colors[ci % len(confetti_colors)]
            draw.rectangle([(cx - cw // 2, cy - ch // 2), (cx + cw // 2, cy + ch // 2)], fill=c_color)

        # 4. Starburst Fireworks Bursts
        bursts = [
            (int(canvas_w * 0.22), int(canvas_h * 0.30), 0.0),
            (int(canvas_w * 0.78), int(canvas_h * 0.28), 0.3),
            (int(canvas_w * 0.50), int(canvas_h * 0.22), 0.6),
        ]
        for bx, by, delay in bursts:
            b_prog = (progress + delay) % 1.0
            if b_prog < 0.6:
                r_dist = int(b_prog * 120)
                num_sparks = 10
                for si in range(num_sparks):
                    ang = (si / num_sparks) * 2 * math.pi
                    sx = bx + int(math.cos(ang) * r_dist)
                    sy = by + int(math.sin(ang) * r_dist * 0.7)
                    if 0 <= sx < canvas_w and 0 <= sy < canvas_h:
                        spark_alpha = max(0, int(255 * (1.0 - b_prog / 0.6)))
                        draw.ellipse([(sx - 3, sy - 3), (sx + 3, sy + 3)], fill=(255, 220, 50, spark_alpha))

    def _draw_field_goal_background(self, draw, canvas_w, canvas_h, p_rgb, s_rgb, frame_idx, progress, cols, rows, logo_img=None, is_ufl_mega=False, frame_canvas=None):
        """Field Goal / Mega Kick: 3D perspective uprights with team logo padded post, flying football trajectory, tip flashes & UFL lightning."""
        # 1. Stadium night sky
        sky_r = min(255, max(0, int(p_rgb[0] * 0.12 + 10)))
        sky_g = min(255, max(0, int(p_rgb[1] * 0.12 + 15)))
        sky_b = min(255, max(0, int(p_rgb[2] * 0.12 + 35)))
        draw.rectangle([(0, 0), (canvas_w, canvas_h)], fill=(sky_r, sky_g, sky_b, 255))

        # Stadium lights
        for lx in (int(canvas_w * 0.12), int(canvas_w * 0.88)):
            draw.ellipse([(lx - 50, -20), (lx + 50, 60)], fill=(255, 255, 220, 50))

        # Turf grass at bottom
        turf_y = int(canvas_h * 0.72)
        draw.rectangle([(0, turf_y), (canvas_w, canvas_h)], fill=(20, 65, 30, 255))
        for gy in range(turf_y, canvas_h, 15):
            draw.rectangle([(0, gy), (canvas_w, min(canvas_h, gy + 7))], fill=(25, 78, 36, 255))
        draw.line([(0, turf_y), (canvas_w, turf_y)], fill=(240, 245, 255, 180), width=3)

        # 2. Upright Dimensions
        cx = canvas_w // 2
        post_bottom = canvas_h - 10
        crossbar_y = int(canvas_h * 0.44)
        upright_top = int(canvas_h * 0.08)
        post_width = 8 if cols >= 8 else 6
        goal_w = int(canvas_w * 0.38) if cols >= 8 else int(canvas_w * 0.46)
        left_x = cx - goal_w // 2
        right_x = cx + goal_w // 2

        goal_color = (255, 215, 0, 255)  # Gold

        # 3. Base Post with Team Padded Protector
        draw.rectangle([(cx - post_width // 2, crossbar_y), (cx + post_width // 2, post_bottom)], fill=goal_color)

        # Team protective pad on lower portion of post
        pad_top = int(canvas_h * 0.60)
        pad_w = post_width + 24
        pad_left = cx - pad_w // 2
        pad_right = cx + pad_w // 2
        draw.rectangle([(pad_left, pad_top), (pad_right, post_bottom)], fill=p_rgb)
        draw.rectangle([(pad_left, pad_top), (pad_right, post_bottom)], outline=s_rgb, width=2)

        # Mini team logo on pad
        if logo_img and frame_canvas:
            pad_h = post_bottom - pad_top
            max_pad_logo = min(pad_w - 4, pad_h - 6)
            if max_pad_logo >= 12:
                try:
                    mini_logo = logo_img.resize((max_pad_logo, max_pad_logo), Image.Resampling.BILINEAR)
                    ml_x = cx - max_pad_logo // 2
                    ml_y = pad_top + (pad_h - max_pad_logo) // 2
                    frame_canvas.alpha_composite(mini_logo, (ml_x, ml_y))
                except Exception:
                    pass

        # 4. Crossbar & Uprights
        draw.rectangle([(left_x, crossbar_y - post_width // 2), (right_x, crossbar_y + post_width // 2)], fill=goal_color)
        draw.rectangle([(left_x - post_width // 2, upright_top), (left_x + post_width // 2, crossbar_y)], fill=goal_color)
        draw.rectangle([(right_x - post_width // 2, upright_top), (right_x + post_width // 2, crossbar_y)], fill=goal_color)

        # 5. UFL Lightning Bolt Effects (Electric Blue & Gold Sparks)
        if is_ufl_mega:
            lightning_color = (120, 210, 255, 255) if (frame_idx % 2 == 0) else (255, 220, 50, 255)
            for bolt_x in (left_x, right_x):
                for by in range(upright_top, crossbar_y, 25):
                    offset_x = 10 if (by // 25 + frame_idx) % 2 == 0 else -10
                    draw.line([(bolt_x, by), (bolt_x + offset_x, by + 12), (bolt_x, by + 25)], fill=lightning_color, width=3)

        # 6. Animated Football Trajectory (Perspective Arc)
        kick_progress = min(1.0, progress * 1.5)
        ball_y = int(canvas_h + 20 - kick_progress * (canvas_h * 0.70))
        drift = int(math.sin(kick_progress * math.pi) * 12)
        ball_x = cx + drift
        ball_size = max(8, int(26 * (1.0 - kick_progress * 0.55)))

        # Comet tail behind ball if UFL Super Kick
        if is_ufl_mega and kick_progress > 0.1:
            for t_i in range(5):
                tail_progress = max(0, kick_progress - t_i * 0.05)
                ty = int(canvas_h + 20 - tail_progress * (canvas_h * 0.70))
                tx = cx + int(math.sin(tail_progress * math.pi) * 12)
                tw = max(4, int(ball_size * 0.8 - t_i * 2))
                t_color = (255, 140, 20, max(0, 200 - t_i * 40)) if (t_i % 2 == 0) else (100, 200, 255, max(0, 200 - t_i * 40))
                draw.ellipse([(tx - tw, ty - tw), (tx + tw, ty + tw)], fill=t_color)

        # Draw the Football (Leather brown oval with white laces)
        draw.ellipse([(ball_x - ball_size, ball_y - ball_size // 2), (ball_x + ball_size, ball_y + ball_size // 2)], fill=(150, 70, 25, 255), outline=(90, 40, 15, 255))
        draw.line([(ball_x - ball_size // 2, ball_y), (ball_x + ball_size // 2, ball_y)], fill=(255, 255, 255, 255), width=2)
        draw.line([(ball_x, ball_y - 3), (ball_x, ball_y + 3)], fill=(255, 255, 255, 255), width=1)

        # 7. Tip Strobe Flashes ("IT'S GOOD!") when ball crosses
        if kick_progress > 0.55:
            flash_on = ((frame_idx // 2) % 2 == 0)
            f_color = (255, 255, 255, 255) if flash_on else (255, 220, 50, 255)
            f_r = 14 if flash_on else 8
            for tip_x in (left_x, right_x):
                draw.ellipse([(tip_x - f_r, upright_top - f_r), (tip_x + f_r, upright_top + f_r)], fill=f_color)

    def _draw_football_background(self, draw, canvas_w, canvas_h, p_rgb, s_rgb, frame_idx, progress, cols, rows):
        """Football: Gridiron turf mower bands, yard chalk lines, hash marks, yard numbers, and endzone slashes."""
        bg_r = min(255, max(0, int(p_rgb[0] * 0.15 + 16)))
        bg_g = min(255, max(0, int(p_rgb[1] * 0.15 + 50)))
        bg_b = min(255, max(0, int(p_rgb[2] * 0.15 + 20)))
        draw.rectangle([(0, 0), (canvas_w, canvas_h)], fill=(bg_r, bg_g, bg_b, 255))

        # Mower grass bands
        stripe_h = 35
        for y in range(0, canvas_h, stripe_h * 2):
            draw.rectangle([(0, y), (canvas_w, min(canvas_h, y + stripe_h))], fill=(bg_r + 6, bg_g + 10, bg_b + 6, 255))

        # Yard lines every 100px (column boundaries)
        font_yard = get_cached_font(14)
        yard_labels = ["G", "10", "20", "30", "40", "50", "40", "30", "20", "10", "G"]
        for c in range(cols + 1):
            x = c * 100
            draw.line([(x, 0), (x, canvas_h)], fill=(240, 245, 255, 140), width=2)
            if c < cols:
                for hx in range(x + 20, x + 100, 20):
                    draw.line([(hx, 10), (hx, 22)], fill=(240, 245, 255, 110), width=2)
                    draw.line([(hx, canvas_h - 22), (hx, canvas_h - 10)], fill=(240, 245, 255, 110), width=2)

                label = yard_labels[c % len(yard_labels)]
                draw.text((x + 50, 16), label, fill=(230, 240, 255, 120), anchor="mm", font=font_yard)
                draw.text((x + 50, canvas_h - 16), label, fill=(230, 240, 255, 120), anchor="mm", font=font_yard)

        # Endzone diagonal hazard stripes on outermost columns
        pulse = (math.sin(progress * math.pi * 6) + 1) / 2
        ez_alpha = int(40 + 50 * pulse)
        for c_idx in (0, cols - 1):
            ez_x = c_idx * 100
            for off in range(-100, 200, 30):
                draw.line([(ez_x + off, 0), (ez_x + off + 50, canvas_h)], fill=(s_rgb[0], s_rgb[1], s_rgb[2], ez_alpha), width=8)

    def _draw_basketball_background(self, draw, canvas_w, canvas_h, p_rgb, s_rgb, frame_idx, progress, cols, rows):
        """Basketball: Hardwood parquet planks, court circles/arcs, and arena backboard buzzer LED border."""
        bg_r = min(255, max(0, int(p_rgb[0] * 0.2 + 36)))
        bg_g = min(255, max(0, int(p_rgb[1] * 0.2 + 22)))
        bg_b = min(255, max(0, int(p_rgb[2] * 0.2 + 10)))
        draw.rectangle([(0, 0), (canvas_w, canvas_h)], fill=(bg_r, bg_g, bg_b, 255))

        # Parquet plank strips
        for py in range(0, canvas_h, 25):
            shade = 8 if (py // 25) % 2 == 0 else -6
            draw.rectangle([(0, py), (canvas_w, py + 24)], fill=(
                min(255, max(0, bg_r + shade)),
                min(255, max(0, bg_g + shade)),
                min(255, max(0, bg_g + shade)),
                255
            ))

        # Court markings
        cx, cy = canvas_w // 2, canvas_h // 2
        draw.ellipse([(cx - 75, cy - 75), (cx + 75, cy + 75)], outline=(255, 255, 255, 60), width=2)
        draw.line([(cx, 0), (cx, canvas_h)], fill=(255, 255, 255, 60), width=2)

        # 3-Point key arcs on sides
        draw.arc([(-60, 20), (140, canvas_h - 20)], start=270, end=90, fill=(255, 255, 255, 50), width=2)
        draw.arc([(canvas_w - 140, 20), (canvas_w + 60, canvas_h - 20)], start=90, end=270, fill=(255, 255, 255, 50), width=2)

        # Backboard Buzzer LED Perimeter Border
        strobe_on = ((frame_idx // 2) % 2 == 0)
        led_color = (255, 30, 30, 255) if strobe_on else (255, 175, 20, 255)
        draw.rectangle([(0, 0), (canvas_w - 1, canvas_h - 1)], outline=led_color, width=5)

    def _draw_baseball_background(self, draw, canvas_w, canvas_h, p_rgb, s_rgb, frame_idx, progress, cols, rows):
        """Baseball: Stadium night ambiance, animated diamond base run loop, baseball stitch curves, and starbursts."""
        bg_r = min(255, max(0, int(p_rgb[0] * 0.2 + 8)))
        bg_g = min(255, max(0, int(p_rgb[1] * 0.2 + 14)))
        bg_b = min(255, max(0, int(p_rgb[2] * 0.2 + 30)))
        draw.rectangle([(0, 0), (canvas_w, canvas_h)], fill=(bg_r, bg_g, bg_b, 255))

        # Diamond base paths
        home_pt = (canvas_w // 2, int(canvas_h * 0.88))
        first_pt = (int(canvas_w * 0.82), canvas_h // 2)
        second_pt = (canvas_w // 2, int(canvas_h * 0.14))
        third_pt = (int(canvas_w * 0.18), canvas_h // 2)

        draw.polygon([home_pt, first_pt, second_pt, third_pt], outline=(230, 220, 190, 110), width=2)

        # Sequentially glowing bases (Home -> 1st -> 2nd -> 3rd -> Home)
        active_base_idx = int(progress * 12) % 4
        bases = [home_pt, first_pt, second_pt, third_pt]
        for idx, (bx, by) in enumerate(bases):
            is_active = (idx == active_base_idx)
            b_color = (255, 240, 100, 255) if is_active else (220, 225, 235, 160)
            bw = 10 if is_active else 6
            draw.polygon([(bx, by - bw), (bx + bw, by), (bx, by + bw), (bx - bw, by)], fill=b_color)

        # Red curved baseball stitches
        for side_x in (int(canvas_w * 0.12), int(canvas_w * 0.88)):
            direction = 1 if side_x > canvas_w // 2 else -1
            for sy in range(20, canvas_h - 20, 25):
                draw.line([(side_x, sy), (side_x + direction * 15, sy - 8)], fill=(220, 40, 40, 160), width=2)

        # Fireworks sparks from center
        spark_count = 12
        pulse_r = 50 + int(progress * 180) % 120
        for s_i in range(spark_count):
            ang = (s_i / spark_count) * 2 * math.pi + (progress * math.pi)
            sx = int(canvas_w // 2 + math.cos(ang) * pulse_r)
            sy = int(canvas_h // 2 + math.sin(ang) * (pulse_r * 0.6))
            if 0 <= sx < canvas_w and 0 <= sy < canvas_h:
                draw.ellipse([(sx - 3, sy - 3), (sx + 3, sy + 3)], fill=(255, 220, 80, 200))

    def _draw_hockey_background(self, draw, canvas_w, canvas_h, p_rgb, s_rgb, frame_idx, progress, cols, rows):
        """Hockey: Ice rink with skate marks, red/blue ice lines, and top-row NHL goal horn sirens."""
        bg_r = min(255, max(0, int(p_rgb[0] * 0.18 + 12)))
        bg_g = min(255, max(0, int(p_rgb[1] * 0.18 + 32)))
        bg_b = min(255, max(0, int(p_rgb[2] * 0.18 + 60)))
        draw.rectangle([(0, 0), (canvas_w, canvas_h)], fill=(bg_r, bg_g, bg_b, 255))

        # Skate scratches
        for sc_i in range(8):
            sx1 = (sc_i * 110 + frame_idx * 5) % canvas_w
            sy1 = (sc_i * 45) % canvas_h
            draw.line([(sx1, sy1), (sx1 + 40, sy1 + 15)], fill=(230, 245, 255, 50), width=1)

        # Ice lines (Red center line, blue lines)
        draw.line([(canvas_w // 2, 0), (canvas_w // 2, canvas_h)], fill=(220, 30, 30, 160), width=3)
        if cols >= 8:
            draw.line([(int(canvas_w * 0.25), 0), (int(canvas_w * 0.25), canvas_h)], fill=(0, 110, 230, 150), width=3)
            draw.line([(int(canvas_w * 0.75), 0), (int(canvas_w * 0.75), canvas_h)], fill=(0, 110, 230, 150), width=3)

        # Top-Row Goal Horn Siren Beacons (Classic NHL Goal Siren)
        siren_h = 45
        draw.rectangle([(0, 0), (canvas_w, siren_h)], fill=(20, 5, 5, 200))
        draw.line([(0, siren_h), (canvas_w, siren_h)], fill=(255, 40, 40, 220), width=2)
        for c in range(cols):
            beacon_x = c * 100 + 50
            siren_on = ((frame_idx + c) % 3) == 0
            beacon_color = (255, 30, 30, 255) if siren_on else (255, 160, 20, 200)
            bw = 14 if siren_on else 8
            draw.ellipse([(beacon_x - bw, 22 - bw // 2), (beacon_x + bw, 22 + bw // 2)], fill=beacon_color)

    def _draw_soccer_background(self, draw, canvas_w, canvas_h, p_rgb, s_rgb, frame_idx, progress, cols, rows):
        """Soccer: Pitch lawn mower bands, stadium center circle, and expanding net ripple shockwaves."""
        bg_r = min(255, max(0, int(p_rgb[0] * 0.15 + 14)))
        bg_g = min(255, max(0, int(p_rgb[1] * 0.15 + 55)))
        bg_b = min(255, max(0, int(p_rgb[2] * 0.15 + 22)))
        draw.rectangle([(0, 0), (canvas_w, canvas_h)], fill=(bg_r, bg_g, bg_b, 255))

        # Mower grass stripes
        for y in range(0, canvas_h, 40):
            if (y // 40) % 2 == 0:
                draw.rectangle([(0, y), (canvas_w, min(canvas_h, y + 40))], fill=(bg_r + 8, bg_g + 14, bg_b + 8, 255))

        # Center circle and pitch line
        cx, cy = canvas_w // 2, canvas_h // 2
        draw.ellipse([(cx - 70, cy - 70), (cx + 70, cy + 70)], outline=(245, 255, 245, 80), width=2)
        draw.line([(cx, 0), (cx, canvas_h)], fill=(245, 255, 245, 80), width=2)

        # Expanding Net Ripple Shockwaves
        ripple_r = int((progress * 380 + (frame_idx % 8) * 20) % 300)
        alpha = max(0, int(120 * (1.0 - ripple_r / 300)))
        draw.ellipse([(cx - ripple_r, cy - ripple_r // 2), (cx + ripple_r, cy + ripple_r // 2)], outline=(255, 255, 255, alpha), width=2)

    def _draw_default_background(self, draw, canvas_w, canvas_h, p_rgb, s_rgb, frame_idx, progress, cols, rows):
        """Default: Dynamic speed stripes and team color pulse strobe."""
        pulse = math.sin(progress * math.pi * 6)
        strobe_intensity = int(30 + 45 * max(0, pulse))
        bg_fill = (
            min(255, p_rgb[0] + strobe_intensity),
            min(255, p_rgb[1] + strobe_intensity),
            min(255, p_rgb[2] + strobe_intensity),
            255
        )
        draw.rectangle([(0, 0), (canvas_w, canvas_h)], fill=bg_fill)

        stripe_offset = int((frame_idx * 18) % 100)
        for x_line in range(-100, canvas_w + 100, 80):
            draw.line(
                [(x_line + stripe_offset, 0), (x_line + stripe_offset + 40, canvas_h)],
                fill=(s_rgb[0], s_rgb[1], s_rgb[2], 60),
                width=12
            )

