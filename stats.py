"""
stats.py
--------
SessionStats — tracks live session statistics and persists the high score.

OOP Concept: Encapsulation — all stat mutation goes through clean methods;
             Persistence via JSON so data survives between runs.
"""

import json
import os
import logging
from datetime import datetime

STATS_FILE = os.path.join(os.path.dirname(__file__), "stats.json")

BALLS_PER_OVER = 6


class SessionStats:
    """
    Tracks the current session's cricket statistics.

    Attributes
    ----------
    runs       : int  — total runs (hits) this session
    balls      : int  — total balls faced
    misses     : int  — balls that beat the bat
    high_score : int  — all-time best score (loaded from JSON)
    _start_ts  : str  — ISO timestamp of session start
    """

    def __init__(self):
        self.runs        = 0
        self.balls       = 0
        self.misses      = 0
        self._start_ts   = datetime.now().isoformat(timespec="seconds")

        # Load persisted high score
        data             = self._load_file()
        self.high_score  = data.get("high_score", 0)
        self.total_games = data.get("total_games", 0)

    # ── Recording ──────────────────────────────────────────────────────────

    def record_hit(self, runs_scored: int = 1) -> None:
        """Call when batsman hits the ball."""
        self.runs  += runs_scored
        self.balls += 1
        if self.runs > self.high_score:
            self.high_score = self.runs
            self._save_file()

    def record_miss(self) -> None:
        """Call when ball passes the bat without a hit."""
        self.balls  += 1
        self.misses += 1

    def record_game_end(self) -> None:
        """Persist stats at end of game."""
        self.total_games += 1
        self._save_file()

    # ── Derived stats ───────────────────────────────────────────────────────

    @property
    def overs(self) -> int:
        """Complete overs bowled."""
        return self.balls // BALLS_PER_OVER

    @property
    def balls_in_over(self) -> int:
        """Balls since last complete over (0-5)."""
        return self.balls % BALLS_PER_OVER

    @property
    def run_rate(self) -> float:
        """Runs per over."""
        if self.overs == 0:
            return 0.0
        return round(self.runs / self.overs, 2)

    @property
    def strike_rate(self) -> float:
        """Runs per 100 balls."""
        if self.balls == 0:
            return 0.0
        return round((self.runs / self.balls) * 100, 1)

    # ── Display helpers ─────────────────────────────────────────────────────

    def overs_str(self) -> str:
        """e.g.  '2.4'  (2 complete overs, 4 balls)."""
        return f"{self.overs}.{self.balls_in_over}"

    def summary_dict(self) -> dict:
        return {
            "runs":        self.runs,
            "balls":       self.balls,
            "misses":      self.misses,
            "overs":       self.overs_str(),
            "run_rate":    self.run_rate,
            "strike_rate": self.strike_rate,
            "high_score":  self.high_score,
        }

    # ── Persistence ─────────────────────────────────────────────────────────

    def _save_file(self) -> None:
        """Write high score and total games to JSON file."""
        try:
            data = {
                "high_score":   self.high_score,
                "total_games":  self.total_games,
                "last_updated": datetime.now().isoformat(timespec="seconds"),
            }
            with open(STATS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.warning(f"Could not save stats: {e}")

    @staticmethod
    def _load_file() -> dict:
        """Read JSON stats file; return empty dict if missing."""
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE) as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"Could not load stats: {e}")
        return {}
