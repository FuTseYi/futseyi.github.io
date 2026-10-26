#!/usr/bin/env python3
"""Minimal Markdown → static HTML builder. No JavaScript rendering needed."""
from __future__ import annotations
import json
import re
from datetime import date
from html import escape
from pathlib import Path
import markdown

ROOT=Path(__file__).resolve().parent.parent
CONTENT=ROOT/"content"/"posts"
OUTPUT=ROOT/"blog"
BASE="https://futseyi.github.io"
LAYOUT='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{description}"><meta name="theme-color" content="#f7f8fa"><title>{title} · Xieyi Fu</title><link rel="canonical" href="{canonical}"><link rel="icon" href="/assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/style.css"><script src="/assets/main.js" defer></script></head><body><a class="skip" href="#content">Skip to content</a><div class="site-shell"><header class="header"><a class="wordmark" href="/"><span class="monogram">F<span class="dot">.</span></span><span>Xieyi Fu <span class="light">/ Shine</span></span></a><nav aria-label="Main navigation"><a href="/">Home</a><a href="/#research">Research</a><a href="/#projects">Projects</a><a class="active" href="/blog/">Writing</a><a href="mailto:hello@futseyi.com" class="nav-contact">Contact ↗</a></nav><button class="theme-toggle" type="button" aria-label="Toggle color theme">◐</button></header><main id="content" class="blog-container">{body}</main><footer class="footer"><span>© <span id="year">2026</span> Xieyi Fu.</span><span>Designed to stay simple. Built for the long run.</span><a href="/">Home ↑</a></footer></div></body></html>'''
def frontmatter(source):
    if not source.startswith("---\n"):
        return {},source
    match=re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n",source,re.S)
    if not match: raise ValueError("Invalid YAML-like frontmatter")
    meta={}
    for line in match.group(1).splitlines():
        if ":" not in line: continue
        key,value=line.split(":",1)
        meta[key.strip()]=value.strip().strip("'\"")
    return meta,source[match.end():]
def render(title,description,canonical,body):
    return LAYOUT.format(title=escape(title,quote=True),description=escape(description,quote=True),canonical=escape(canonical,quote=True),body=body)
def main():
    OUTPUT.mkdir(exist_ok=True)
    posts=[]
    md=markdown.Markdown(extensions=["extra","codehilite","toc","sane_lists"])
    for source in sorted(CONTENT.glob("*.md")):
        slug=source.stem
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",slug): raise ValueError("Use lowercase ASCII slug: "+slug)
        meta,text=frontmatter(source.read_text(encoding="utf-8"))
        if meta.get("draft","").lower()=="true": continue
        title=meta.get("title",slug.replace("-"," ").title())
        pub=meta.get("date","")
        if pub: date.fromisoformat(pub)
        description=meta.get("description","")
        md.reset()
        article=md.convert(text)
        url="/blog/"+slug+"/"
        header='<a class="back-link" href="/blog/">← All writing</a><div class="article-head"><h1>'+escape(title)+'</h1><p class="post-date">'+escape(pub)+'</p><p class="blog-description">'+escape(description)+'</p></div>'
        html='<article class="article">'+article+'</article>'
        dest=OUTPUT/slug
        dest.mkdir(parents=True,exist_ok=True)
        (dest/"index.html").write_text(render(title,description,BASE+url,header+html+'<div class="article-footer"><a class="back-link" href="/blog/">← Back to writing</a></div>'),encoding="utf-8")
        posts.append({"title":title,"date":pub,"description":description,"slug":slug,"url":url,"tags":[t.strip() for t in meta.get("tags","").split(",") if t.strip()]})
    posts.sort(key=lambda p:(p["date"],p["slug"]),reverse=True)
    entries=''.join('<a class="blog-entry" href="'+escape(p["url"],quote=True)+'"><span class="post-date">'+escape(p["date"])+'</span><h2>'+escape(p["title"])+' ↗</h2><p>'+escape(p["description"])+'</p></a>' for p in posts)
    body='<a class="back-link" href="/">← Home</a><p class="section-index" style="margin-top:40px">WRITING / NOTES</p><h1>Thoughts in progress<span style="color:var(--accent)">.</span></h1><p class="blog-description">Technical experiments, project notes, and occasional reflections — kept deliberately simple.</p><div style="margin-top:40px">'+(entries or '<p>No articles published yet.</p>')+'</div>'
    (OUTPUT/"index.html").write_text(render("Writing","Technical writing and project notes",BASE+"/blog/",body),encoding="utf-8")
    (OUTPUT/"posts.json").write_text(json.dumps(posts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    from xml.sax.saxutils import escape as xml_escape
    pages=[BASE+"/", BASE+"/blog/"]+[BASE+p["url"] for p in posts]
    sitemap='<?xml version="1.0" encoding="UTF-8"?>\\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\\n'+''.join("<url><loc>"+xml_escape(url)+"</loc></url>\\n" for url in pages)+"</urlset>\\n"
    (ROOT/"sitemap.xml").write_text(sitemap,encoding="utf-8")
    print("Built",len(posts),"articles")
if __name__=="__main__":main()
