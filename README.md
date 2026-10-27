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
│   ├── scripts/               # Markdown builder and link validator
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
mkdir -p _site && cp index.html robots.txt sitemap.xml _site/ && cp -r assets blog _site/
python .github/scripts/verify.py
python -m http.server 8000
```

Open http://localhost:8000. To edit your introduction or projects, modify `index.html`; for visual styling, modify `assets/style.css`.

For AI maintenance instructions, see [AGENTS.md](AGENTS.md). The previous website at `FuTseYi/My-Website` remains untouched.

## Images and local links

Upload images into `assets/images/` (create the folder as needed) and use a root-relative URL in Markdown, for example `![Experiment output](/assets/images/example.webp)`. The deployment verifies that referenced local files exist. External images and links remain external. Keep images reasonably compressed and provide meaningful alt text.

The homepage links directly to Writing rather than hardcoding a particular newest post. `posts/` is the single source for the article list, which is refreshed on every deployment.
