# FuTseYi · Personal Homepage

A clean academic-style personal website with an integrated Markdown-based Writing section. No Astro, React, Tailwind, or CMS. A small, framework-free JavaScript file progressively enhances navigation.

**Live site:** https://futseyi.github.io/ · **Writing:** https://futseyi.github.io/blog/

## Structure

```text
.
├── index.html                  # Personal homepage
├── assets/                     # Shared CSS, navigation script and favicon
├── posts/                      # Author your articles here (Markdown)
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

Commit the file to `main`; GitHub Actions will generate the Writing index and the post page. The GitHub Pages source **must be set to GitHub Actions** in Settings → Pages. The `blog/` output is generated automatically during GitHub Actions deployment and is intentionally ignored by Git. Add or edit articles only in `posts/`; do not commit generated HTML.

## Local preview (Windows and macOS)

Open `index.html` directly in your browser. **No installation, terminal or local server is required** to preview the homepage, styling, section navigation or mobile menu. The Writing links open the published website because Markdown posts are built by GitHub Actions. This offline preview does not rebuild Writing.

To change your bio or projects, edit `index.html`; for appearance, edit `assets/style.css`. Push to `main` to publish your site and build Writing automatically.

For optional build verification when developing the blog, use the same steps as `.github/workflows/deploy.yml`, which runs on GitHub Actions (Ubuntu). There is no platform-specific preview script to maintain.

For AI maintenance instructions, see [AGENTS.md](AGENTS.md). The previous website at `FuTseYi/My-Website` remains untouched.

## Images and local links

Upload images into `assets/images/` (create the folder as needed) and use a root-relative URL in Markdown, for example `![Experiment output](/assets/images/example.webp)`. The deployment verifies referenced local images (including responsive `srcset` images) and site links; malformed article metadata stops publication before regeneration. External images and links remain external. Keep images reasonably compressed and provide meaningful alt text.

The homepage links directly to Writing rather than hardcoding a particular newest post. `posts/` is the single source for the article list, which is refreshed on every deployment.

## Navigation

The homepage and Writing share a compact sticky navigation, mobile menu, and shared CSS. `assets/site.js` handles the mobile menu, keyboard dismissal, and current-section highlighting, without a JavaScript framework. The floating page directory appears on wide displays only. Edit layout in `index.html`, page styling in `assets/style.css`, and Writing's common markup in `.github/scripts/build.py`.
