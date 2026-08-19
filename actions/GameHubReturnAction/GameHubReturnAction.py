"""
DeckSports GameHubReturnAction
1-tap navigation key to return from the full-screen Game Hub dashboard back to origin profile page.
"""

import os
from functools import lru_cache
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
from PIL import Image, ImageDraw, ImageFont

from src.backend.PluginManager.ActionBase import ActionBase
from src.backend.DeckManagement.InputIdentifier import Input
import globals as gl

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

class GameHubReturnAction(ActionBase):
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

    def get_deck_controller_to_use(self):
        if getattr(self, "deck_controller", None):
            return self.deck_controller
        if hasattr(gl, "deck_manager") and getattr(gl.deck_manager, "deck_controller", None):
            controllers = gl.deck_manager.deck_controller
            if controllers:
                return controllers[0]
        return None

    def on_ready(self):
        self._ensure_media_control()
        self.plugin_base.sports_service.add_listener(self.on_game_state_updated)
        GLib.idle_add(self.update_display)

    def on_remove(self):
        self.plugin_base.sports_service.remove_listener(self.on_game_state_updated)

    def on_game_state_updated(self, league_key: str, team_id: str, state: GameState):
        GLib.idle_add(self.update_display)

    def on_key_down(self):
        if hasattr(self.plugin_base.sports_service, "celebration_manager"):
            if self.plugin_base.sports_service.celebration_manager.is_animating:
                self.plugin_base.sports_service.celebration_manager.cancel()
        controller = self.get_deck_controller_to_use()
        if not controller:
            return

        origin = self.plugin_base.sports_service.get_origin_page(id(controller))
        if origin:
            if hasattr(origin, "get_name") and hasattr(origin, "json_path"):
                controller.load_page(origin)
                return
            elif isinstance(origin, str) and os.path.isfile(origin):
                page_obj = gl.page_manager.get_page(origin, deck_controller=controller)
                if page_obj:
                    controller.load_page(page_obj)
                    return

        # Fallback to default page for this deck
        serial = ""
        if hasattr(controller, "deck") and hasattr(controller.deck, "get_serial_number"):
            try:
                serial = controller.deck.get_serial_number()
            except Exception:
                pass
        elif hasattr(controller, "serial_number"):
            try:
                serial = controller.serial_number() if callable(controller.serial_number) else str(controller.serial_number)
            except Exception:
                pass

        default_page = gl.page_manager.get_default_page(serial) if serial else None
        if default_page and os.path.isfile(default_page):
            page_obj = gl.page_manager.get_page(default_page, deck_controller=controller)
            if page_obj:
                controller.load_page(page_obj)
                return

        # Fallback to first available non-GameHub user page
        for p in gl.page_manager.get_pages():
            if os.path.isfile(p) and not ("GameHub" in os.path.basename(p)):
                page_obj = gl.page_manager.get_page(p, deck_controller=controller)
                if page_obj:
                    controller.load_page(page_obj)
                    return

    def update_display(self):
        if not self.get_is_present():
            return
        self._ensure_media_control()

        img = Image.new("RGBA", (100, 100), (20, 22, 28, 255))
        draw = ImageDraw.Draw(img)

        # 1. Header Banner
        draw.rectangle([(0, 0), (100, 24)], fill=(32, 38, 50, 255))
        draw.line([(0, 24), (100, 24)], fill=(50, 60, 80, 255), width=1)

        font_hdr = get_bundled_font(11)
        draw.text((50, 12), "RETURN", fill=(180, 200, 230, 255), anchor="mm", font=font_hdr)

        # 2. Main Body: Back arrow & EXIT
        font_exit = get_bundled_font(15)
        draw.text((50, 50), "< EXIT", fill=(56, 189, 248, 255), anchor="mm", font=font_exit)

        # 3. Footer: Main Profile
        draw.rectangle([(0, 78), (100, 100)], fill=(16, 18, 22, 255))
        draw.line([(0, 78), (100, 78)], fill=(45, 50, 60, 255), width=1)

        font_foot = get_bundled_font(10)
        draw.text((50, 89), "Main Profile", fill=(140, 150, 170, 255), anchor="mm", font=font_foot)

        # Outer key border
        draw.rectangle([(0, 0), (99, 99)], outline=(40, 90, 130, 255), width=1)

        self.set_media(image=img)
