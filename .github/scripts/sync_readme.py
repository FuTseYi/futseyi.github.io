#!/usr/bin/env python3
"""Generate mirrored READMEs from index.html and published posts. Standard library only."""
import argparse
import base64
import json
import os
import re
from datetime import date
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[2]
SITE="https://futseyi.github.io"
def md(fragment):
    fragment=re.sub(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>',lambda m:"["+re.sub(r"<[^>]*>","",m[2]).strip()+"]("+m[1]+")",fragment,flags=re.S|re.I)
    fragment=re.sub(r"<strong>(.*?)</strong>",r"**\1**",fragment,flags=re.S|re.I)
    return unescape(" ".join(re.sub(r"<[^>]+>","",fragment).split()))
def read_home():
    html=(ROOT/"index.html").read_text(encoding="utf-8")
    bio=re.search(r'<div\s+class="bio"\s*>(.*?)</div>',html,re.S)
    if not bio: raise ValueError("index.html: missing .bio")
    paragraphs=[md(x) for x in re.findall(r"<p\b[^>]*>(.*?)</p>",bio[1],re.S)]
    email=re.search(r'href="mailto:([^"]+)"',html)
    canonical=re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"',html)
    if not paragraphs or not email or not canonical: raise ValueError("index.html: missing bio, email or canonical")
    return paragraphs,email[1],canonical[1].rstrip("/")
def read_posts():
    found=[]
    for file in (ROOT/"posts").glob("*.md"):
        raw=file.read_text(encoding="utf-8")
        fm=re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n",raw,re.S)
        if not fm: raise ValueError(f"{file.name}: missing frontmatter")
        fields={}
        for line in fm[1].splitlines():
            if ":" in line and not line.lstrip().startswith("#"):
                k,v=line.split(":",1);fields[k.strip()]=v.strip().strip("'\"")
        if fields.get("draft","false").lower() in ("true","yes","1"):continue
        if not fields.get("title") or not fields.get("date"):raise ValueError(f"{file.name}: missing title or date")
        dt=date.fromisoformat(fields["date"])
        if dt>date.today():continue
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",file.stem):raise ValueError(f"Invalid article slug: {file.stem}")
        found.append((dt,file.stem,fields["title"]))
    found.sort(reverse=True)
    return [f"- [{title}]({SITE}/blog/{slug}/)" for _,slug,title in found[:3]]
def render():
    paragraphs,email,website=read_home()
    posts=read_posts()
    return (
      '## *About* ![](https://raw.githubusercontent.com/FuTseYi/FuTseYi/main/assets/i-am-Shine.svg)\n\n'
      '- ***Currently exploring new things, occasionally pretending I know what I’m doing.***\n'
      +''.join(f"- {paragraph}\n" for paragraph in paragraphs)
      +'- *Lang: English, Mandarin, Cantonese.*\n'
      +f'- *Contact: [{email}](mailto:{email})*\n\n'
      +'## *Website*\n\n'
      +f'- Visit 『*[{website.removeprefix("https://")}]({website}/)*』 to learn more about me.\n\n'
      +'## *Motto*\n\n'
      +'<img src="https://raw.githubusercontent.com/FuTseYi/FuTseYi/main/assets/emoji-wink.png" align="right" width="6%" alt="Winking emoji">\n\n'
      +'- *Freiheit als Autonomie — Freedom through autonomy.*\n'
      +'- *People can retire, but the spirit cannot retire. - Gundam*\n\n'
      +'## Latest Posts\n\n'
      +'\n'.join(posts or ["No published articles yet."])+'\n\n'
      +'<a href="https://visit-counter.futseyi.workers.dev/status?path=https%3A%2F%2Fgithub.com%2FFuTseYi" target="_blank" rel="noopener noreferrer">\n'
      +'  <img src="https://visit-counter.futseyi.workers.dev/api/combined?path=https%3A%2F%2Fgithub.com%2FFuTseYi" alt="Visitor badge" />\n'
      +'</a>\n\n'
      +'<sub>Powered by <a href="https://github.com/FuTseYi/Cloudflare-D1-Visit-Counter">Cloudflare-D1-Visit-Counter</a></sub>\n'
    )
def request(method,url,token,body=None):
    req=Request(url,method=method,data=json.dumps(body).encode() if body is not None else None,headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json","User-Agent":"FuTseYi-readme-sync"})
    with urlopen(req,timeout=30) as response:return json.load(response)
def sync_profile(text,token):
    url="https://api.github.com/repos/FuTseYi/FuTseYi/contents/README.md"
    current=request("GET",url,token)
    if base64.b64decode(current["content"]).decode("utf-8")==text:
        print("Profile README already matches.");return
    request("PUT",url,token,{"message":"docs: sync README from personal website","branch":"main","sha":current["sha"],"content":base64.b64encode(text.encode("utf-8")).decode("ascii")})
    print("Updated FuTseYi/FuTseYi README")
def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--sync-profile",action="store_true")
    args=arg.parse_args()
    text=render();path=ROOT/"README.md"
    if not path.exists() or path.read_text(encoding="utf-8")!=text:
        path.write_text(text,encoding="utf-8");print("Generated website README")
    else:print("Website README unchanged")
    if args.sync_profile:
        token=os.environ.get("PROFILE_README_TOKEN","")
        if not token:raise SystemExit("PROFILE_README_TOKEN is missing; configure one fine-grained token scoped to FuTseYi/FuTseYi with Contents:write")
        sync_profile(text,token)
if __name__=="__main__":main()
