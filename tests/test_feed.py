"""No-network regressions for the reviewed-revision / root-tree distinction."""
from types import SimpleNamespace
import json
import subprocess
import pytest
import refresh_feed


def payload():
    return dict(sha='a'*40,commit=dict(tree=dict(sha='b'*40),committer=dict(date='2026-10-11T20:00:00Z')),
                html_url='https://github.com/example/repository/commit/'+'a'*40)


@pytest.mark.parametrize('review,changed',[('a'*40,False),('b'*40,False),('c'*40,True)])
def test_accept_commit_or_root_tree_revision(monkeypatch,review,changed):
    monkeypatch.setattr(refresh_feed.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout=json.dumps(payload())))
    result=refresh_feed.check(dict(repo='example',tree_sha=review))
    assert result['status']=='metadata_checked'
    assert result['changed_since_review'] is changed
    assert result['reviewed_revision']==review
    assert 'score' not in result and 'leaderboard' not in result


@pytest.mark.parametrize('body',['{}','not-json'])
def test_malformed_metadata_cannot_look_fresh(monkeypatch,body):
    monkeypatch.setattr(refresh_feed.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout=body))
    assert refresh_feed.check(dict(repo='example',tree_sha='a'*40))['status']=='unavailable'


def test_failed_api_request_cannot_look_fresh(monkeypatch):
    monkeypatch.setattr(refresh_feed.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=1,stderr='request failed'))
    assert refresh_feed.check(dict(repo='example',tree_sha='a'*40))['status']=='unavailable'


def test_timed_out_api_request_cannot_look_fresh(monkeypatch):
    def timeout(*a,**kw):raise subprocess.TimeoutExpired('gh',30)
    monkeypatch.setattr(refresh_feed.subprocess,'run',timeout)
    assert refresh_feed.check(dict(repo='example',tree_sha='a'*40))['status']=='unavailable'
