# FuTseYi website — AI maintenance rules

The goal is a **small, durable, professional academic homepage**. Avoid adding a framework or complex infrastructure.

- Public identity: **FuTseYi / Shine**. Do not use FuXieyi or copy other researchers' credentials.
- Homepage: `index.html` (semantic HTML, no browser-side JavaScript).
- CSS: `assets/style.css`, shared by the homepage and Writing.
- Articles: `posts/*.md`, with title, date, description and optional comma-separated tags; optional `draft: true`.
- Publish: `.github/scripts/build.py` (Python-Markdown), `.github/workflows/deploy.yml` (GitHub Pages).
- Legacy/fallback published HTML: `blog/`; do **not** delete the directory or change `/blog/` links.
- Keep the design understated, readable, accessible, and responsive. Prefer the existing classes, consistent spacing and restrained blue accent.
- NEVER publish private contact details, unsupported achievements, or inferred publications/jobs. Use only the public email: hello@futseyi.com.
- **Important GitHub writes:** when creating a Git tree via the API, ALWAYS specify the current commit's `base_tree_sha`. Without it, unrelated files/directories may disappear. Verify the full tree after updating the branch.
- After edits, run `python .github/scripts/build.py`, check generated `blog/index.html` and article links, then verify the GitHub Pages workflow.
- When adding a post, do not manually edit `blog/index.html`; the Actions build regenerates it. If branch-based publishing is intentionally used, commit the generated `blog/` pages too.
- Do not migrate old `My-Website` content without reviewing privacy, image paths and URL preservation.
