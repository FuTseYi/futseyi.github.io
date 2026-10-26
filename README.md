# Xieyi Fu / Shine — Personal Website

A framework-free, responsive academic portfolio and Markdown blog.

**Homepage:** https://futseyi.github.io/

## Stack
- Plain **HTML + CSS + vanilla JavaScript** (no frontend build chain)
- **Python-Markdown** for Markdown → static HTML
- GitHub Actions + GitHub Pages for continuous deployment
- No database, runtime server, or frontend framework

## Local preview
```bash
python -m pip install -r requirements.txt
python scripts/build.py
python -m http.server 8000
```
Open http://localhost:8000 — using a web server is required for the post index fetch.

## Publishing a post
Add `content/posts/my-new-post.md` with:
```md
---
title: My New Post
date: 2026-10-26
description: A brief summary.
tags: Notes, Technology
---
# Hello!
Markdown content here.
```
Push to `main`. Pages will publish automatically when its Source is set to **GitHub Actions**.

## Project maintenance
See [AGENTS.md](AGENTS.md) for detailed instructions for coding assistants. The previous Astro project remains available separately at `FuTseYi/My-Website` and has not been modified.

## Notes
This repository is a new site, not an automatic full migration of the old blog library. Existing posts and media can be migrated intentionally, keeping old URLs or adding redirects as needed. Project links and CV details should be reviewed periodically.

© Xieyi Fu.
