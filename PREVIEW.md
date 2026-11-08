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
```

On Windows, substitute `py -3` for `python3`.

- `--build-only`: Generate and verify `_site/` without serving it.
- `--port 8766`: Choose another local preview port.

**One authoritative contribution file:** `main/contributions.json` is tracked in Git. GitHub Actions alone calls GitHub GraphQL via `python scripts/sync_activity.py --write-source` on scheduled or manual updates, plus one-time bootstrap when absent; it commits only if the actual entries change. GitHub Actions explicitly builds and publishes GitHub Pages in the same run because GitHub's default `GITHUB_TOKEN` pushes do not launch another Actions workflow. Vercel's existing Git integration deploys the source-data commit automatically. Both hosts run **exactly** `python3 preview.py --build-only`, consuming the same versioned file without a GitHub token or API request during ordinary builds. The generated `_site/contributions.json` is a copy of the tracked data. No `VERCEL_TOKEN`, Deploy Hook, extra Git deployment branch, empty refresh commits, or second source of contribution data is necessary. Different platforms still compile their own HTML output.

Recent Open Contributions is a **display name**, not a 365-day data cutoff. With `GITHUB_TOKEN`, the build queries GitHub's official GraphQL `contributionsCollection.contributionYears` and reads each active calendar year in API-safe intervals. GitHub-attributed commits, opened pull requests and issues, submitted reviews, and original repository creations (not Fork creations) are grouped by repository, limited to publicly visible repositories, and sorted by the user's latest qualifying contribution timestamp. Each repository appears once. The only deliberate exclusions are `FuTseYi/futseyi.github.io` and `FuTseYi/FuTseYi`. There is no historical age or displayed-repository count cap; the homepage initially shows three entries, then each **Show more** reveals the next incomplete calendar year of repository activity (skipping empty years). **Show less** restores the initial three. A Fork is not included merely because it was created, but qualifying commits, PRs, issues or reviews remain eligible on any public repository, including a Fork.

This uses GitHub's **official contribution criteria**, not a complete event log: ordinary comments, discussions and unmerged branch commits may not count. The GraphQL API limits repositories per category, so overfull periods are recursively split rather than silently truncated. The versioned `contributions.json` is the portable, authoritative input; ordinary builds never call GitHub and fail rather than silently showing an incomplete list when the file is missing or invalid. GitHub API errors during scheduled sync leave the last committed data unchanged. The `updated_at` timestamp records the last actual data change, not every no-op check. Do not commit tokens, `_site/`, generated blog HTML, or search indexes; **do** commit the small canonical `contributions.json`. GitHub history retains old versions, so be mindful when previously public repositories are later made private.

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
