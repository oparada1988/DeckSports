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

            if os.path.isdir(bundled_pages_dir):
                for filename in os.listdir(bundled_pages_dir):
                    if filename.endswith(".json"):
                        src_path = os.path.join(bundled_pages_dir, filename)
                        dst_path = os.path.join(pages_dir, filename)
                        if not os.path.exists(dst_path):
                            shutil.copy2(src_path, dst_path)
        except Exception:
            pass

