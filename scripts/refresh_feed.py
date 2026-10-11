"""Public GitHub metadata feed only. Never guesses live competition scores."""
import _path  # noqa: F401
from gems65.common import ROOT, write_json
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess


def check(item):
    repo='buffedlizard55-lab/'+item['repo']
    try:
        proc=subprocess.run(['gh','api',f'repos/{repo}/commits/main'],capture_output=True,text=True,timeout=30)
        if proc.returncode:
            return dict(repository=repo,status='unavailable',message=proc.stderr.strip()[:200])
        obj=json.loads(proc.stdout)
        tree=obj['commit']['tree']['sha']
        return dict(repository=repo,status='metadata_checked',latest_commit=obj['sha'],
                    tree_sha=tree,commit_time=obj['commit']['committer']['date'],
                    changed_since_review=item['tree_sha'] not in {obj['sha'], tree},
                    reviewed_revision=item['tree_sha'],url=obj['html_url'])
    except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError,KeyError) as e:
        return dict(repository=repo,status='unavailable',message=type(e).__name__)


def main():
    inventory=json.loads((ROOT/'evidence/repository_inventory.json').read_text())
    with ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(check,inventory['repositories']))
    now=datetime.now(timezone.utc).isoformat()
    feed=dict(checked_at=now,scope='GitHub commit metadata only; no live site, leaderboard, score or cap verification',
              organizer_verified=False,training_rerun=False,submission_slots_used=0,
              repositories=results,checked=sum(r['status']=='metadata_checked' for r in results),
              unavailable=sum(r['status']!='metadata_checked' for r in results),
              changed=sum(r.get('changed_since_review',False) for r in results))
    write_json(ROOT/'docs/data/feed.json',feed)
    print(json.dumps({k:v for k,v in feed.items() if k!='repositories'},indent=2))

if __name__=='__main__':main()
