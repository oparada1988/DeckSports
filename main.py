"""
DeckSports Plugin for StreamController
Live sports scoreboard, game clock, and full-screen Game Hub dashboard across NFL, NBA, MLB, MLS, UFL, NHL, NCAA, and WNBA.
"""

import os
import shutil
import globals as gl
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.PluginManager.ActionHolder import ActionHolder
from src.backend.PluginManager.ActionHolderGroup import ActionHolderGroup
from src.backend.DeckManagement.InputIdentifier import Input
from src.backend.PluginManager.ActionInputSupport import ActionInputSupport

try:
    from .backend.SportsService import SportsService
    from .actions.GameHubAction.GameHubAction import GameHubAction
    from .actions.TeamScoreAction.TeamScoreAction import TeamScoreAction
    from .actions.GameHubReturnAction.GameHubReturnAction import GameHubReturnAction
    from .actions.LineScoreAction.LineScoreAction import LineScoreAction
    from .actions.PlayerLeaderAction.PlayerLeaderAction import PlayerLeaderAction
    from .actions.SituationAction.SituationAction import SituationAction
    from .actions.TeamStatsCompareAction.TeamStatsCompareAction import TeamStatsCompareAction
    from .actions.ScoringSummaryAction.ScoringSummaryAction import ScoringSummaryAction
except (ImportError, ValueError):
    from backend.SportsService import SportsService
    from actions.GameHubAction.GameHubAction import GameHubAction
    from actions.TeamScoreAction.TeamScoreAction import TeamScoreAction
    from actions.GameHubReturnAction.GameHubReturnAction import GameHubReturnAction
    from actions.LineScoreAction.LineScoreAction import LineScoreAction
    from actions.PlayerLeaderAction.PlayerLeaderAction import PlayerLeaderAction
    from actions.SituationAction.SituationAction import SituationAction
    from actions.TeamStatsCompareAction.TeamStatsCompareAction import TeamStatsCompareAction
    from actions.ScoringSummaryAction.ScoringSummaryAction import ScoringSummaryAction

class DeckSports(PluginBase):
    def __init__(self):
        super().__init__()

        # Shared backend data manager
        self.sports_service = SportsService()
        self.sports_service.plugin_base = self
        if hasattr(self.sports_service, "celebration_manager"):
            self.sports_service.celebration_manager.plugin_base = self

        # Auto-provision pre-built Game Hub templates into StreamController pages folder on first launch
        self._auto_provision_pages()

        # 1. Register GameHubAction (Master Coordinator / Clock / Possession / Navigation)
        self.game_hub_holder = ActionHolder(
            plugin_base=self,
            action_base=GameHubAction,
            action_id_suffix="GameHubAction",
            action_name="Game Hub / Clock",
            icon=Gtk.Image.new_from_file(os.path.join(self.PATH, "assets", "game_hub_clock.png")),
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNSUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(self.game_hub_holder)

        # 2. Register TeamScoreAction (Left / Right Live Score & Logo)
        self.team_score_holder = ActionHolder(
            plugin_base=self,
            action_base=TeamScoreAction,
            action_id_suffix="TeamScoreAction",
            action_name="Team Score / Logo",
            icon=Gtk.Image.new_from_file(os.path.join(self.PATH, "assets", "team_score_logo.png")),
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNSUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(self.team_score_holder)

        # 3. Register GameHubReturnAction (1-Tap Exit back to Profile)
        self.return_holder = ActionHolder(
            plugin_base=self,
            action_base=GameHubReturnAction,
            action_id_suffix="GameHubReturnAction",
            action_name="Game Hub Return / Exit",
            icon=Gtk.Image.new_from_file(os.path.join(self.PATH, "assets", "action_return.png")),
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNSUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(self.return_holder)

        # 4. Register LineScoreAction (Quarter / Period Breakdown)
        self.line_score_holder = ActionHolder(
            plugin_base=self,
            action_base=LineScoreAction,
            action_id_suffix="LineScoreAction",
            action_name="Line Score / Period Breakdown",
            icon=Gtk.Image.new_from_file(os.path.join(self.PATH, "assets", "action_linescore.png")),
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNSUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(self.line_score_holder)

        # 5. Register PlayerLeaderAction (Headshot & Category Leader)
        self.leader_holder = ActionHolder(
            plugin_base=self,
            action_base=PlayerLeaderAction,
            action_id_suffix="PlayerLeaderAction",
            action_name="Player Leader Card",
            icon=Gtk.Image.new_from_file(os.path.join(self.PATH, "assets", "action_leader.png")),
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNSUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(self.leader_holder)

        # 6. Register SituationAction (Down & Dist, Red Zone, Count, PP)
        self.situation_holder = ActionHolder(
            plugin_base=self,
            action_base=SituationAction,
            action_id_suffix="SituationAction",
            action_name="Situational Radar / Info",
            icon=Gtk.Image.new_from_file(os.path.join(self.PATH, "assets", "action_situation.png")),
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNSUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(self.situation_holder)

        # 7. Register TeamStatsCompareAction (Total Yards, 3rd Downs, Turnovers, Standings)
        self.stats_holder = ActionHolder(
            plugin_base=self,
            action_base=TeamStatsCompareAction,
            action_id_suffix="TeamStatsCompareAction",
            action_name="Team Stats Comparison",
            icon=Gtk.Image.new_from_file(os.path.join(self.PATH, "assets", "action_stats.png")),
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNSUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(self.stats_holder)

        # 8. Register ScoringSummaryAction (Last Scoring Play / Drives)
        self.scoring_holder = ActionHolder(
            plugin_base=self,
            action_base=ScoringSummaryAction,
            action_id_suffix="ScoringSummaryAction",
            action_name="Scoring Summary / Drives",
            icon=Gtk.Image.new_from_file(os.path.join(self.PATH, "assets", "action_scoring.png")),
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNSUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(self.scoring_holder)

        # Group sub-actions inside a clean, collapsed folder in the sidebar
        self.dashboard_group = ActionHolderGroup(
            group_name="Game Hub Dashboard Components",
            action_holders=[
                self.return_holder,
                self.line_score_holder,
                self.leader_holder,
                self.situation_holder,
                self.stats_holder,
                self.scoring_holder
            ]
        )
        self.add_action_holder_group(self.dashboard_group)

        # Register plugin with StreamController
        self.register(
            plugin_name="DeckSports",
            github_repo="https://github.com/oparada1988/DeckSports",
            plugin_version="1.0.0",
            app_version="1.5.0-beta"
        )

    def get_selector_icon(self) -> Gtk.Widget:
        icon_path = os.path.join(self.PATH, "assets", "plugin_icon.png")
        if os.path.exists(icon_path):
            return Gtk.Image.new_from_file(icon_path)
        return super().get_selector_icon()

    def _auto_provision_pages(self):
        try:
            if not hasattr(gl, "DATA_PATH") or not gl.DATA_PATH:
                return

            pages_dir = os.path.join(gl.DATA_PATH, "pages")
            os.makedirs(pages_dir, exist_ok=True)
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            bundled_pages_dir = os.path.join(plugin_dir, "pages")

            if not os.path.isdir(bundled_pages_dir):
                return

            controllers = []
            if hasattr(gl, "deck_manager") and getattr(gl.deck_manager, "deck_controller", None):
                controllers = gl.deck_manager.deck_controller

            # Defer provisioning until actual hardware is connected
            if not controllers:
                return

            has_xl = False
            has_mk2 = False

            for c in controllers:
                key_count = 0
                if hasattr(c, "deck") and hasattr(c.deck, "key_count"):
                    try:
                        key_count = c.deck.key_count()
                    except Exception:
                        pass
                elif hasattr(c, "inputs") and Input.Key in c.inputs:
                    key_count = len(c.inputs[Input.Key])

                if key_count >= 32:
                    has_xl = True
                elif key_count > 0:
                    has_mk2 = True

            src_xl = os.path.join(bundled_pages_dir, "DeckSports_GameHub_XL.json")
            dst_xl = os.path.join(pages_dir, "DeckSports_GameHub_XL.json")
            src_mk2 = os.path.join(bundled_pages_dir, "DeckSports_GameHub_MK2.json")
            dst_mk2 = os.path.join(pages_dir, "DeckSports_GameHub_MK2.json")

            # 1. Provision XL template if XL deck is present
            if has_xl and os.path.isfile(src_xl) and not os.path.exists(dst_xl):
                shutil.copy2(src_xl, dst_xl)

            # 2. Provision MK2 template if 15-key deck is present
            if has_mk2 and os.path.isfile(src_mk2) and not os.path.exists(dst_mk2):
                shutil.copy2(src_mk2, dst_mk2)

            # 3. Clean up unneeded template if only one deck format is used
            if has_xl and not has_mk2:
                if os.path.exists(dst_mk2):
                    try:
                        os.remove(dst_mk2)
                    except Exception:
                        pass
            elif has_mk2 and not has_xl:
                if os.path.exists(dst_xl):
                    try:
                        os.remove(dst_xl)
                    except Exception:
                        pass
        except Exception:
            pass

    def get_settings_area(self) -> Adw.PreferencesGroup:
        main_group = Adw.PreferencesGroup(
            title="DeckSports Global Settings & Testing",
            description="Manage global celebration animation rules and test animations on connected hardware."
        )

        settings = self.get_settings()

        # 1. Global Celebrations Master Switch
        celeb_row = Adw.SwitchRow(
            title="Global Score Celebrations",
            subtitle="Master toggle for full-deck scoring animations across all Game Hubs"
        )
        celeb_row.set_active(settings.get("enable_celebrations", True))
        def on_celeb_toggled(row, _pspec):
            st = self.get_settings()
            st["enable_celebrations"] = row.get_active()
            self.set_settings(st)
        celeb_row.connect("notify::active", on_celeb_toggled)
        main_group.add(celeb_row)

        # 2. Animation Testing Station Combo
        anim_types = [
            ("🏈 Football Touchdown (Gridiron & Confetti)", "football_td"),
            ("🎯 3D Field Goal (\"IT'S GOOD!\")", "field_goal"),
            ("⚡ UFL 4-Point Mega Kick (Lightning)", "ufl_mega"),
            ("🏀 Basketball 3-Pointer / Slam Dunk", "basketball"),
            ("⚾ Baseball Home Run / Grand Slam", "baseball"),
            ("🏒 Hockey Goal / Red Siren", "hockey"),
            ("⚽ Soccer Goal / Penalty Kick", "soccer"),
            ("🏆 Victory Jumbotron (Post-Game Finale)", "victory")
        ]

        anim_model = Gtk.StringList.new([name for name, _ in anim_types])
        test_combo_row = Adw.ComboRow(
            title="Celebration Animation Test Suite",
            subtitle="Select any sport celebration to preview live on your Stream Deck",
            model=anim_model
        )
        test_combo_row.set_selected(0)
        main_group.add(test_combo_row)

        # 3. Trigger Preview Button Row
        test_action_row = Adw.ActionRow(
            title="Preview Selected Animation",
            subtitle="Broadcasts the full-deck animation to your deck and UI preview"
        )
        play_btn = Gtk.Button(label="Play Live Preview")
        play_btn.set_valign(Gtk.Align.CENTER)
        play_btn.add_css_class("suggested-action")

        def on_play_clicked(_btn):
            selected_idx = test_combo_row.get_selected()
            if 0 <= selected_idx < len(anim_types):
                _, anim_key = anim_types[selected_idx]
                if hasattr(self.sports_service, "celebration_manager"):
                    self.sports_service.celebration_manager.trigger_test_preview(anim_key)

        play_btn.connect("clicked", on_play_clicked)
        test_action_row.add_suffix(play_btn)
        main_group.add(test_action_row)

        return main_group

    def on_uninstall(self) -> None:
        """
        Cleans up and deletes provisioned Game Hub page templates when the plugin is uninstalled.
        """
        super().on_uninstall()
        try:
            if hasattr(gl, "DATA_PATH") and gl.DATA_PATH:
                pages_dir = os.path.join(gl.DATA_PATH, "pages")
                for page_name in ("DeckSports_GameHub_XL.json", "DeckSports_GameHub_MK2.json"):
                    page_path = os.path.join(pages_dir, page_name)
                    if os.path.exists(page_path):
                        try:
                            os.remove(page_path)
                        except Exception:
                            pass
        except Exception:
            pass

