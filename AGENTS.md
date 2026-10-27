# FuTseYi website — AI maintenance rules

The goal is a **small, durable, professional academic homepage**. Avoid adding a framework or complex infrastructure.

- Public identity: **FuTseYi / Shine**. Do not use FuXieyi or copy other researchers' credentials.
- Homepage: `index.html` (semantic HTML, no browser-side JavaScript).
- CSS: `assets/style.css`, shared by the homepage and Writing.
- Articles: `posts/*.md`, with title, date, description and optional comma-separated tags; optional `draft: true`.
- Publish: `.github/scripts/build.py` (Python-Markdown), `.github/workflows/deploy.yml` (GitHub Pages).
- Generated HTML: `blog/` is ignored and regenerated from `posts/` during deployment; never commit generated HTML.
- Keep the design understated, readable, accessible, and responsive. Prefer the existing classes, consistent spacing and restrained blue accent.
- NEVER publish private contact details, unsupported achievements, or inferred publications/jobs. Use only the public email: hello@futseyi.com.
- **Important GitHub writes:** when creating a Git tree via the API, ALWAYS specify the current commit's `base_tree_sha`. Without it, unrelated files/directories may disappear. Verify the full tree after updating the branch.
- After edits, install `Markdown>=3.7,<4`, run `python .github/scripts/build.py`, stage the output as the workflow does, and run `python .github/scripts/verify.py`. The generator validates post metadata before replacing old generated files; a clean rebuild removes pages for deleted posts. Broken local images/links should fail verification.
- When adding a post, edit `posts/*.md`; the build will regenerate `blog/index.html` and article pages automatically.
- Do not migrate old `My-Website` content without reviewing privacy, image paths and URL preservation.

- Homepage Writing section links to the blog index intentionally; do not hardcode the latest article in the homepage.
- Images for Markdown articles belong in `assets/images/` with root-absolute paths. Keep alt text and use optimized image files.
