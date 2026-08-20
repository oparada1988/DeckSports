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


def get_celebration_text(league_key: str, sport_slug: str, score_delta: int = 0) -> str:
    """Determine dynamic celebration text based on sport and scoring magnitude."""
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

    if sport == "football":
        if score_delta >= 6:
            return "TOUCHDOWN!"
        elif score_delta == 3:
            return "FIELD GOAL!"
        elif score_delta == 2:
            return "SAFETY!"
        elif score_delta == 1:
            return "EXTRA POINT!"
        return "TOUCHDOWN!"

    elif sport == "basketball":
        if score_delta >= 3:
            return "3-POINTER!"
        elif score_delta == 1:
            return "FREE THROW!"
        elif score_delta == 2:
            return "SLAM DUNK!"
        return "SLAM DUNK!"

    elif sport == "baseball":
        if score_delta >= 4:
            return "GRAND SLAM!"
        elif score_delta in (2, 3):
            return "HOME RUN!"
        elif score_delta == 1:
            return "RUN SCORED!"
        return "HOME RUN!"

    elif sport == "hockey":
        return "GOAL!"

    elif sport == "soccer":
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
        score_delta: int = 0
    ):
        with self._lock:
            if self.is_animating:
                return
            self.is_animating = True
            self._cancel_requested = False

        threading.Thread(
            target=self._run_celebration_worker,
            args=(league_key, team_name, team_abbrev, primary_color, alt_color, celebration_text, score_delta),
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
        score_delta: int
    ):
        try:
            sport_slug = ""
            if league_key in LEAGUES:
                sport_slug = LEAGUES[league_key].sport_slug

            if not celebration_text:
                celebration_text = get_celebration_text(league_key, sport_slug, score_delta)

            controller = None
            if hasattr(gl, "deck_manager") and getattr(gl.deck_manager, "deck_controller", None):
                controllers = gl.deck_manager.deck_controller
                if controllers:
                    controller = controllers[0]

            if not controller:
                return

            # Guard: Only play score celebration on Game Hub pages
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

            # Check if celebrations are enabled on the active GameHub action
            all_actions = active_page.get_all_actions()
            celebrations_enabled = True
            for act in all_actions:
                if act.__class__.__name__ == "GameHubAction":
                    settings = act.get_settings()
                    celebrations_enabled = settings.get("enable_celebrations", True)
                    break

            if not celebrations_enabled:
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

            total_frames = 45
            fps = 15
            frame_duration = 1.0 / fps

            logo_img = None
            teams = self.sports_service.get_teams(league_key)
            my_team = next((t for t in teams if t.get("name") == team_name or t.get("abbreviation") == team_abbrev), None)
            if my_team and my_team.get("logo_url"):
                logo_img = self.sports_service.get_image(my_team["logo_url"], max_size=(180, 180))

            p_rgb = primary_color[:3] if len(primary_color) >= 3 else (0, 53, 148)
            s_rgb = alt_color[:3] if len(alt_color) >= 3 else (200, 205, 215)

            # Select background renderer based on sport
            sport_renderer = self._draw_default_background
            if sport_slug == "football":
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

                # Abort if active page has changed away from GameHub
                current_page = getattr(controller, "active_page", None)
                if not current_page or ("GameHub" not in str(getattr(current_page, "name", "")) and "GameHub" not in str(getattr(current_page, "json_path", ""))):
                    break

                frame_canvas = Image.new("RGBA", (canvas_w, canvas_h), (16, 18, 24, 255))
                draw = ImageDraw.Draw(frame_canvas)
                progress = frame_idx / total_frames

                # Draw sport-specific background
                sport_renderer(draw, canvas_w, canvas_h, p_rgb, s_rgb, frame_idx, progress, cols, rows)

                # Center pulsing logo
                if logo_img:
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

                # Subtitle (Team Name)
                draw.text(
                    (canvas_w // 2, banner_y2 - 22),
                    f"{team_name.upper()}",
                    fill=(200, 225, 255, 255),
                    anchor="mm",
                    font=font_sub
                )

                if direct_hardware:
                    # Direct hardware native USB sweep: convert full canvas to RGB once per frame to eliminate redundant per-tile allocations
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
        """Invalidates cached hardware image hashes and forces full-matrix scoreboard refresh."""
        try:
            if controller and hasattr(controller, "inputs"):
                for input_type in controller.inputs:
                    for inp in controller.inputs[input_type]:
                        if hasattr(inp, "_last_img_hash"):
                            inp._last_img_hash = None

            self.sports_service.notify_all()

            active_page = getattr(controller, "active_page", None) if controller else None
            if active_page and hasattr(active_page, "get_all_actions"):
                for act in active_page.get_all_actions():
                    if hasattr(act, "update_display") and callable(act.update_display):
                        try:
                            act.update_display()
                        except Exception:
                            pass

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

