"""Preserve legacy URLs while replacing the superseded no-data state truthfully."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_current_and_legacy_card_urls_are_identical():
    assert (ROOT/'docs/data/run-card.json').read_bytes()==(ROOT/'evidence/run_card.json').read_bytes()
    assert (ROOT/'docs/data/run_card.json').read_bytes()==(ROOT/'evidence/run_card.json').read_bytes()


def test_current_card_is_negative_despite_completed_experiments_and_format_pass():
    card=json.loads((ROOT/'docs/data/run-card.json').read_text())
    assert card['verdict']=='negative'
    assert card['eligible_for_download'] is False
    assert card['approved_for_weekly_slot'] is False
    assert card['experiments_completed']==3 and card['submission_slots_used']==0
    assert card['evidence_class']=='HOLDOUT-DTI'
    assert card['holdout']['sar']['dti'] is not None
    assert card['validator']['status']=='PASS'
    assert card['registry']['complete'] is False
    assert card['registry']['literal_gate_passed'] is False
    assert card['em_converged'] is False
    assert len(card['raster_sha256'])==64
    assert len(card['note'])<=140


def test_original_preflight_card_is_preserved_as_history_not_current_state():
    card=json.loads((ROOT/'evidence/history/preflight-run-card-main-7275bde.json').read_text())
    assert card['verdict']=='negative'
    assert card['submission']['name'] is None
    assert card['holdout_dti']['score'] is None
    assert card['model_comparison']['status']=='NOT RUN'
    assert card['raster_sha256'] is None
    assert len(card['submission']['note'])<=140
