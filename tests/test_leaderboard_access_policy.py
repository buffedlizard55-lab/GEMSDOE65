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
        self.assertIn("Verify Pages uses workflow deployments", workflow)

    def test_site_links_out_without_storing_leaderboard_rows(self) -> None:
        home = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/", home)
        self.assertIn("https://www.drivendata.org/termsofuse/", home)
        self.assertFalse((ROOT / "docs" / "data" / "leaderboard.json").exists())
        self.assertFalse((ROOT / "scripts" / "refresh_leaderboard.py").exists())


if __name__ == "__main__":
    unittest.main()


def test_scheduled_metadata_is_github_only_and_never_writes_main():
    workflow=(ROOT/'.github/workflows/metadata.yml').read_text()
    script=(ROOT/'scripts/refresh_feed.py').read_text()
    assert "cron: '22 7 * * *'" in workflow
    assert 'git add docs/data/feed.json' in workflow
    assert 'git push origin arena/f09c3103-gemsdoe65' in workflow
    assert 'git push origin main' not in workflow
    assert 'run_experiments.py' not in workflow
    assert 'drivendata.org' not in workflow+script
    assert "f'repos/{repo}/commits/main'" in script
