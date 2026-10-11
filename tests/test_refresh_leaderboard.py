import json
import tempfile
import unittest
from pathlib import Path

from scripts.refresh_leaderboard import parse_leaderboard_html, write_json_atomic


FIXTURE = """
<!doctype html><html><body><table>
<thead><tr><th>Rank</th><th>Team members</th><th>Participant</th><th>Best<br>public<br>DW-Tversky</th><th>Shared work</th></tr></thead>
<tbody>
<tr><td>#1</td><td></td><td><a>sample_team</a><br>one day ago<br>4 submissions</td><td>0.8123</td><td></td></tr>
<tr><td>#2</td><td></td><td>another_team<br>two days ago<br>2 submissions</td><td>0.0765</td><td></td></tr>
</tbody></table></body></html>
"""


class LeaderboardParserTests(unittest.TestCase):
    def test_parses_scores_and_first_participant_line(self):
        result = parse_leaderboard_html(FIXTURE, "2026-10-11T00:00:00Z")
        self.assertEqual(result["retrieved_at_utc"], "2026-10-11T00:00:00Z")
        self.assertFalse(result["receipt_available"])
        self.assertIn("PUBLIC-LEADERBOARD-OBSERVATION", result["evidence_label"])
        self.assertEqual(
            result["rows"],
            [
                {"rank": 1, "participant": "sample_team", "public_dti": "0.8123"},
                {"rank": 2, "participant": "another_team", "public_dti": "0.0765"},
            ],
        )

    def test_fails_closed_when_table_layout_changes(self):
        with self.assertRaisesRegex(ValueError, "headers"):
            parse_leaderboard_html("<html><table><tr><td>unexpected</td></tr></table></html>")

    def test_rejects_score_outside_metric_range(self):
        html = FIXTURE.replace("0.8123", "1.2")
        with self.assertRaisesRegex(ValueError, "invalid public DTI"):
            parse_leaderboard_html(html)

    def test_rejects_duplicate_rank(self):
        html = FIXTURE.replace("<td>#2</td>", "<td>#1</td>")
        with self.assertRaisesRegex(ValueError, "Duplicate leaderboard rank"):
            parse_leaderboard_html(html)

    def test_atomic_json_write(self):
        payload = parse_leaderboard_html(FIXTURE, "2026-10-11T00:00:00Z")
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "nested" / "feed.json"
            write_json_atomic(target, payload)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), payload)
            self.assertFalse(target.with_name(target.name + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
