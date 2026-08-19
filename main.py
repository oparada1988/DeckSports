"""
DeckSports Plugin for StreamController
Live sports scoreboard, game clock, and full-screen Game Hub dashboard across NFL, NBA, MLB, MLS, UFL, NHL, NCAA, and WNBA.
"""

import os
import shutil
import globals as gl

from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.PluginManager.ActionHolder import ActionHolder
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

        # Auto-provision pre-built Game Hub templates into StreamController pages folder on first launch
        self._auto_provision_pages()

        # 1. Register GameHubAction (Master Coordinator / Clock / Possession / Navigation)
        self.game_hub_holder = ActionHolder(
            plugin_base=self,
            action_base=GameHubAction,
            action_id_suffix="GameHubAction",
            action_name="Game Hub / Clock",
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
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNSUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNTESTED,
            }
        )
        self.add_action_holder(self.scoring_holder)

        # Register plugin with StreamController
        self.register(
            plugin_name="DeckSports",
            github_repo="https://github.com/oparada1988/DeckSports",
            plugin_version="1.0.0",
            app_version="1.5.0-beta"
        )

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

            # Determine connected hardware models
            needs_xl = False
            needs_mk2 = False

            controllers = []
            if hasattr(gl, "deck_manager") and getattr(gl.deck_manager, "deck_controller", None):
                controllers = gl.deck_manager.deck_controller

            if controllers:
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
                        needs_xl = True
                    elif key_count == 15:
                        needs_mk2 = True
                    else:
                        # Fallback for standard 15-key decks
                        needs_mk2 = True
            else:
                # Early initialization before decks connect: check deck settings files
                deck_settings_dir = os.path.join(gl.DATA_PATH, "settings", "decks")
                if os.path.isdir(deck_settings_dir):
                    deck_files = [f for f in os.listdir(deck_settings_dir) if f.endswith(".json")]
                    # If user has only 1 deck configured or decks present, check for XL serials or sizes
                    # Default: allow provision when actions initialize
                    needs_xl = True
                    needs_mk2 = True
                else:
                    needs_xl = True
                    needs_mk2 = True

            # 1. Provision XL template if needed
            src_xl = os.path.join(bundled_pages_dir, "DeckSports_GameHub_XL.json")
            dst_xl = os.path.join(pages_dir, "DeckSports_GameHub_XL.json")
            if needs_xl and os.path.isfile(src_xl) and not os.path.exists(dst_xl):
                shutil.copy2(src_xl, dst_xl)

            # 2. Provision MK2 template if needed
            src_mk2 = os.path.join(bundled_pages_dir, "DeckSports_GameHub_MK2.json")
            dst_mk2 = os.path.join(pages_dir, "DeckSports_GameHub_MK2.json")
            if needs_mk2 and os.path.isfile(src_mk2) and not os.path.exists(dst_mk2):
                shutil.copy2(src_mk2, dst_mk2)

            # 3. If user has only an XL, remove any unneeded MK2 template
            if controllers and needs_xl and not needs_mk2:
                if os.path.exists(dst_mk2):
                    try:
                        os.remove(dst_mk2)
                    except Exception:
                        pass
            elif controllers and needs_mk2 and not needs_xl:
                if os.path.exists(dst_xl):
                    try:
                        os.remove(dst_xl)
                    except Exception:
                        pass
        except Exception:
            pass

