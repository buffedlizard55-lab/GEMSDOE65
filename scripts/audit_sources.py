"""Read the public source behind each requested site, without claiming a live visit."""
import _path  # noqa: F401
from gems65.common import ROOT, write_json
import json
import subprocess
import hashlib
import concurrent.futures
from html.parser import HTMLParser
from datetime import datetime, timezone

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0; self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag in {'script','style'}: self.skip+=1
        if tag=='a':
            href=dict(attrs).get('href','')
            if href: self.links.append(href)
    def handle_endtag(self, tag):
        if tag in {'script','style'}: self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip(): self.parts.append(data.strip())

def main():
    inventory=json.loads((ROOT/'evidence/repository_inventory.json').read_text())
    def inspect(repo):
        name=repo['repo']
        tree=ROOT/f'.cache/audit/{name}-tree.json'
        if not tree.exists():
            tree.parent.mkdir(parents=True,exist_ok=True)
            result=subprocess.run(['gh','api',f'repos/buffedlizard55-lab/{name}/git/trees/{repo["tree_sha"]}?recursive=1'],capture_output=True,text=True)
            if result.returncode:return dict(repo=name,status='source_tree_missing')
            tree.write_text(result.stdout)
        entries={x['path']:x for x in json.loads(tree.read_text())['tree'] if x['type']=='blob'}
        path=next((p for p in ['docs/index.html','index.html','README.md'] if p in entries),None)
        if path is None:return dict(repo=name,status='no_index')
        blob=entries[path]['sha']
        r=subprocess.run(['gh','api',f'repos/buffedlizard55-lab/{name}/git/blobs/{blob}',
                          '-H','Accept: application/vnd.github.raw+json'],capture_output=True)
        if r.returncode:return dict(repo=name,status='fetch_error',error=r.stderr.decode()[:300])
        text=r.stdout.decode('utf-8',errors='replace')
        p=Text();p.feed(text)
        readable=' '.join(p.parts) if path.endswith('.html') else text
        terms=['propensity','nnpu','sar-em','h33','catalogue','holdout','negative','blocked','duplicate','submission','UNSCORED']
        snippets=[]
        for term in terms:
            i=readable.lower().find(term.lower())
            if i>=0:snippets.append({'term':term,'excerpt':readable[max(0,i-100):i+240]})
        cached=ROOT/'.cache/site_sources'/name/path
        cached.parent.mkdir(parents=True,exist_ok=True);cached.write_bytes(r.stdout)
        return dict(repo=name,status='repository_source_inspected',path=path,git_blob_sha=blob,
            sha256=hashlib.sha256(r.stdout).hexdigest(),bytes=len(r.stdout),tree_sha=repo['tree_sha'],
            review_url=f'https://github.com/buffedlizard55-lab/{name}/blob/{blob}/{path}',
            tree_url=f'https://github.com/buffedlizard55-lab/{name}/tree/{repo["tree_sha"]}',
            expected_site=f'https://buffedlizard55-lab.github.io/{name}/',
            live_site_verified=False,organizer_receipt_verified=False,
            tiff_links=[a for a in p.links if a.lower().split('?')[0].endswith(('.tif','.zip'))],
            snippets=snippets)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        rows=list(pool.map(inspect, inventory['repositories']))
    for row in rows:
        if 'git_blob_sha' in row:
            repo='buffedlizard55-lab/'+row['repo']
            row['blob_api_url']=f'https://api.github.com/repos/{repo}/git/blobs/{row["git_blob_sha"]}'
            row['review_url']=row['blob_api_url']
            ref=row['tree_sha']
            resolved=subprocess.run(['gh','api',f'repos/{repo}/commits/{ref}','--jq','.sha'],capture_output=True,text=True)
            if resolved.returncode==0 and resolved.stdout.strip()==ref:
                row['source_commit_sha']=ref
                row['review_url']=f'https://github.com/{repo}/blob/{ref}/{row["path"]}'
    result=dict(checked_at=datetime.now(timezone.utc).isoformat(),
                method='Pinned GitHub source inspection. Pages host and organizer pages not reachable under sandbox allowlist.',
                scores_status='All prompt/sibling score claims remain unverified without a submission-page receipt.',
                repositories=rows)
    write_json(ROOT/'evidence/site_review.json',result)
    print('Inspected',len(rows),'repository site sources; organizer scores verified: none.')

if __name__=='__main__': main()
