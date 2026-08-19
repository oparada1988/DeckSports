"""
DeckSports CelebrationManager
Full-deck synchronized score celebration animation engine.
Renders full-matrix visual celebration sequences across Stream Deck XL (8x4) and MK.2 (5x3) keypads.
"""

import os
import time
import math
import threading
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
from gi.repository import GLib
import globals as gl

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

class CelebrationManager:
    def __init__(self, sports_service):
        self.sports_service = sports_service
        self.is_animating = False
        self._cancel_requested = False
        self._lock = threading.Lock()

    def cancel(self):
        with self._lock:
            self._cancel_requested = True

    def trigger(self, league_key: str, team_name: str, team_abbrev: str, primary_color: tuple, alt_color: tuple, celebration_text: str = ""):
        with self._lock:
            if self.is_animating:
                return
            self.is_animating = True
            self._cancel_requested = False

        threading.Thread(
            target=self._run_celebration_worker,
            args=(league_key, team_name, team_abbrev, primary_color, alt_color, celebration_text),
            daemon=True
        ).start()

    def _run_celebration_worker(self, league_key: str, team_name: str, team_abbrev: str, primary_color: tuple, alt_color: tuple, celebration_text: str):
        try:
            if not celebration_text:
                if league_key in ("NFL", "UFL", "NCAA_FB"):
                    celebration_text = "TOUCHDOWN!"
                elif league_key in ("NHL", "MLS"):
                    celebration_text = "GOAL!"
                elif league_key in ("MLB",):
                    celebration_text = "HOME RUN!"
                elif league_key in ("NBA", "WNBA", "NCAA_BK"):
                    celebration_text = "SLAM DUNK!"
                else:
                    celebration_text = "SCORE!"

            controller = None
            if hasattr(gl, "deck_manager") and getattr(gl.deck_manager, "deck_controller", None):
                controllers = gl.deck_manager.deck_controller
                if controllers:
                    controller = controllers[0]

            if not controller:
                return

            cols, rows = 8, 4
            key_count = 32
            if hasattr(controller, "deck") and hasattr(controller.deck, "key_count"):
                try:
                    key_count = controller.deck.key_count()
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

            total_frames = 36
            fps = 12
            frame_duration = 1.0 / fps

            logo_img = None
            teams = self.sports_service.get_teams(league_key)
            my_team = next((t for t in teams if t.get("name") == team_name or t.get("abbreviation") == team_abbrev), None)
            if my_team and my_team.get("logo_url"):
                logo_img = self.sports_service.get_image(my_team["logo_url"], max_size=(180, 180))

            p_rgb = primary_color[:3] if len(primary_color) >= 3 else (0, 53, 148)
            s_rgb = alt_color[:3] if len(alt_color) >= 3 else (200, 205, 215)

            for frame_idx in range(total_frames):
                if self._cancel_requested:
                    break

                frame_canvas = Image.new("RGBA", (canvas_w, canvas_h), (16, 18, 24, 255))
                draw = ImageDraw.Draw(frame_canvas)

                progress = frame_idx / total_frames
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

                if logo_img:
                    scale_factor = 1.0 + 0.15 * math.sin(progress * math.pi * 4)
                    scaled_w = int(logo_img.width * scale_factor)
                    scaled_h = int(logo_img.height * scale_factor)
                    scaled_logo = logo_img.resize((scaled_w, scaled_h), Image.Resampling.BILINEAR)
                    lx = (canvas_w - scaled_w) // 2
                    ly = (canvas_h - scaled_h) // 2 - 20
                    frame_canvas.alpha_composite(scaled_logo, (lx, ly))

                banner_y1 = int(canvas_h * 0.48)
                banner_y2 = int(canvas_h * 0.82)
                draw.rectangle([(0, banner_y1), (canvas_w, banner_y2)], fill=(12, 14, 18, 230))
                draw.line([(0, banner_y1), (canvas_w, banner_y1)], fill=(255, 215, 0, 255), width=3)
                draw.line([(0, banner_y2), (canvas_w, banner_y2)], fill=(255, 215, 0, 255), width=3)

                font_title = get_cached_font(52 if cols >= 8 else 36)
                font_sub = get_cached_font(26 if cols >= 8 else 18)

                draw.text((canvas_w // 2 + 3, (banner_y1 + banner_y2) // 2 - 12 + 3), celebration_text, fill=(0, 0, 0, 255), anchor="mm", font=font_title)
                text_color = (255, 255, 255, 255) if (frame_idx % 2 == 0) else (255, 225, 50, 255)
                draw.text((canvas_w // 2, (banner_y1 + banner_y2) // 2 - 12), celebration_text, fill=text_color, anchor="mm", font=font_title)

                draw.text((canvas_w // 2, banner_y2 - 22), f"{team_name.upper()}", fill=(200, 225, 255, 255), anchor="mm", font=font_sub)

                # Slice full canvas into 100x100 tiles
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
                time.sleep(frame_duration)

        except Exception as e:
            import logging
            logging.getLogger("DeckSports").error(f"Error in score celebration animation: {e}")
        finally:
            with self._lock:
                self.is_animating = False
                self._cancel_requested = False
            GLib.idle_add(self.sports_service.notify_all)
