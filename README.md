# FuTseYi · Personal Homepage

A clean academic-style personal website with an integrated Markdown-based Writing section. No Astro, React, Tailwind, CMS, or browser-side JavaScript.

**Live site:** https://futseyi.github.io/ · **Writing:** https://futseyi.github.io/blog/

## Structure

```text
.
├── index.html                  # Personal homepage
├── assets/                     # Shared CSS and favicon
├── posts/                      # Author your articles here (Markdown)
├── blog/                       # Generated HTML (temporary branch-mode fallback)
├── .github/
│   ├── scripts/build.py        # Markdown → HTML + sitemap
│   └── workflows/deploy.yml    # Publish on push
├── AGENTS.md                   # Instructions for AI maintainers
└── README.md
```

## Write a new post

Create `posts/my-new-post.md`:

```markdown
---
title: My new post
date: 2026-10-27
description: A short introduction to the article.
tags: Technology, Notes
---

## Heading

Write normally using **Markdown**.
```

Commit the file to `main`; GitHub Actions will generate the Writing index and the post page. The GitHub Pages source **must be set to GitHub Actions** in Settings → Pages. The current tracked `blog/` pages are retained as an interim fallback because GitHub still reports branch-based Pages builds. **Do not delete them until Settings → Pages → Source is confirmed as GitHub Actions.** Once confirmed, generated HTML can be untracked safely; the workflow will recreate it. When you add or delete articles, the Pages Actions workflow always generates a clean blog tree from `posts/`.

## Local preview

```bash
python -m pip install "Markdown>=3.7,<4"
python .github/scripts/build.py
python -m http.server 8000
```

Open http://localhost:8000. To edit your introduction or projects, modify `index.html`; for visual styling, modify `assets/style.css`.

For AI maintenance instructions, see [AGENTS.md](AGENTS.md). The previous website at `FuTseYi/My-Website` remains untouched.
