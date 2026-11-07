# Development & Preview

The website is built from source into a portable static directory, `_site/`. The current local preview uses Python 3.10 or newer.

## Getting Started

From the repository root:

```powershell
# Windows
py -3 preview.py
```

```sh
# macOS / Linux
python3 preview.py
```

Open <http://127.0.0.1:8765/> or <http://127.0.0.1:8765/blog/>. Saving a source file triggers a rebuild; refresh your browser to see the result. Stop with Ctrl+C, and run only one preview process per checkout.

Dependencies come from `requirements.txt`. If needed, the command installs them into a project-local `.venv` (or the active virtual environment), not the system Python. Initial setup requires internet access and working `venv`/`pip` support. The preview retains the previous successful build if a rebuild fails.

## Building & Output

```sh
python3 preview.py --build-only
python3 preview.py --build-only --refresh-activity
```

On Windows, substitute `py -3` for `python3`.

- `--build-only`: Generate and verify `_site/` without serving it.
- `--refresh-activity`: Fetch fresh public contribution data instead of reusing an available snapshot.
- `--port 8766`: Choose another local preview port.

Vercel uses the repository-owned `vercel.json` to invoke `python3 preview.py --build-only --refresh-activity` and publish `_site/`. GitHub Pages uses the same builder with `--refresh-activity` for its scheduled updates. After a successful scheduled or manually dispatched Pages publish, the workflow creates one empty `chore: refresh website activity` commit on `main` to request a Vercel Git deployment. Ordinary source pushes do not create refresh commits. Keep these hosts as adapters around the one build pipeline.

The contribution list covers public, non-archived repositories with an attributed commit or authored non-draft PR in the past 365 days. It sorts by personal contribution date and shows up to 12 repositories (first three before expanding). With `GITHUB_TOKEN` set in the build environment, commit discovery uses GitHub GraphQL contribution records; otherwise it uses paginated public REST commit search. Pull requests use GitHub's public search API. Token values must be configured in the hosting provider, never committed or exposed to the frontend. GitHub search and contribution APIs have their own indexing and result limits, so this is not a complete all-branches git-history audit. A successful refresh publishes only newly queried contributions after rechecking public repository status; previously published entries are not treated as proof of a current contribution. The GraphQL repository aggregate is bounded, so incomplete coverage falls back to REST search. If refreshing fails, the previous snapshot is reused with expired entries removed and its original timestamp retained. The live site's JSON is the cross-deployment cache, not the ephemeral Vercel build directory.

The same build entry point is used for verification and the current publishing workflow. It generates the blog and search index, synchronizes staged homepage content, and checks the output. Generated `blog/`, `_site/`, and `sitemap.xml` are ignored by Git.

The canonical origin in `index.html` determines generated article URLs, sitemap entries, and README links. Internal navigation uses root-relative paths. Hosting, domain, and credential settings belong outside the portable build.

## Writing & Publishing

Create `posts/my-note/index.md`:

```markdown
---
title: My note
date: 2026-10-28
tags: Notes, Website
---

Article text goes here.
```

`title` and `date` are required; `tags` and `lang` (`zh-CN` or `en`) are optional. The article title becomes the page H1; headings in the body are shifted down one level while retaining their anchors. Dates determine display order, not scheduled publication.

Keep article media beside its source in `posts/my-note/assets/` and link to files such as `assets/example.webp`. Use meaningful alt text for informative images, empty alt text for decorative images, and `<figure>`/`<figcaption>` when a caption is needed. The folder name forms the public URL (`/blog/my-note/`), so avoid changing it after publishing.

Under the current workflows, changes reaching `main` publish the site and trigger README synchronization.

## Browser Verification

Run the build check above for site or publishing changes. The repository's PR workflow additionally runs Python unit tests and Chromium and WebKit browser smoke tests.

Static checks cover generated pages and links but cannot establish visual or interaction correctness. For relevant changes, verify narrow and wide layouts, both color themes, keyboard use, reduced motion, and direct page loads. Exercise same-page and cross-page links, browser Back/Forward, the mobile menu, Blog search, article contents, and code copying. Inspect representative image-, table-, and code-heavy articles when rendering changes.

## Implementation Notes

The generated blog reuses header/footer markup from `index.html`, while `style.css` and `site.js` serve the site as a whole. When Swup is available, same-origin navigation replaces `#main` while shared UI and the WebGL atmosphere remain mounted. Ordinary document navigation remains the fallback if Swup is unavailable.

Page-specific interactions in `site.js` must initialize for incoming content and clean up when that content is replaced. Review listeners, observers, timers, and dialogs for lifecycle leaks when changing navigation. Refer to the source for pinned dependency versions and implementation details rather than duplicating them here.

Preview, article, README, activity and browser regression checks live in `tests/`; generation and validation stay in `scripts/`. The homepage is edited directly in root `index.html`; generated blog pages reuse its header/footer. `scripts/site_build.py` owns this site's isolated content pipeline. No separate template directory or cross-repository runtime is required.
