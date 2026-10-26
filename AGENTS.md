# AI Maintenance Guide

This website is intentionally simple. **Do not introduce Astro, React, Tailwind, Node build tooling, a database, or a CMS** without an explicit request.

## Architecture
- `index.html`: single-page personal homepage (semantic HTML).
- `assets/style.css`: design tokens and all styling, including responsive and dark mode.
- `assets/main.js`: tiny enhancements (theme switch, latest article list).
- `content/posts/*.md`: Markdown source for posts, with a short frontmatter block.
- `scripts/build.py`: converts posts into standalone, indexable HTML, and generates listing JSON.
- `.github/workflows/deploy.yml`: GitHub Pages deployment, no frontend framework.

## Editing
1. Use existing CSS variables and components, preserve visual consistency.
2. Edit HTML directly for personal info, education, research, or projects.
3. Add a `content/posts/my-post.md` file for a new article. Frontmatter fields: title, date (YYYY-MM-DD), description, tags (comma separated); draft: true to exclude.
4. **Never invent credentials, degrees, publications, awards or employment.** Verify facts before adding.
5. Protect private details and personal identifiers; email contact for display is hello@futseyi.com only.
6. Keep accessible semantics, alt text, keyboard navigation, reduced-motion support, and mobile layouts.
7. Prefer no dependencies; only Python-Markdown is used for building posts. Do not inject arbitrary raw HTML into articles from untrusted contributors.
8. Before delivery, run `python -m pip install -r requirements.txt && python scripts/build.py` and review generated `blog/` output.
9. Generated `blog/` files are not committed; GitHub Actions generates them on deploy. Do not modify them manually.
10. Original Astro site is retained separately at `FuTseYi/My-Website` for reference; do not change it unless explicitly requested.

## Publishing
Commit changes to main. GitHub Actions publishes on every push when repository Settings → Pages → Source is **GitHub Actions**. No API keys required.

## Style
Editorial academic portfolio. Quiet navy / blue palette, ample whitespace, understated motion. Prioritize credible content and readable typography over decorative widgets.
