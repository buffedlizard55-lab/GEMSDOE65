from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LeaderboardAccessPolicyTests(unittest.TestCase):
    def test_pages_workflow_does_not_schedule_or_fetch_leaderboard(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("refresh_leaderboard.py", workflow)
        self.assertNotIn("drivendata.org/competitions/306/competition-doe-gems/leaderboard", workflow)

    def test_site_links_out_without_storing_leaderboard_rows(self) -> None:
        home = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/", home)
        self.assertIn("https://www.drivendata.org/termsofuse/", home)
        self.assertFalse((ROOT / "docs" / "data" / "leaderboard.json").exists())
        self.assertFalse((ROOT / "scripts" / "refresh_leaderboard.py").exists())


if __name__ == "__main__":
    unittest.main()
