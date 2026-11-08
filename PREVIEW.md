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

Production is published only by `.github/workflows/deploy.yml` on `main` pushes, scheduled refreshes (1st and 15th of each month), or manual dispatch. GitHub Actions runs `python preview.py --build-only --refresh-activity` **once**, using its scoped `GITHUB_TOKEN`, and verifies the resulting `_site/`. The same `_site/` is uploaded to GitHub Pages and copied unchanged to Vercel's Build Output API `.vercel/output/static/` with `config.json` version 3. Vercel is staged with `vercel deploy --prebuilt --prod --skip-domain`, then promoted to the production domain after Pages succeeds. The `vercel.json` Git deployment switch disables independent Vercel Git builds; no Deploy Hook, empty refresh commit, second site build, or separate Vercel GitHub credential is needed.

**One-time activation:** create a Vercel Access Token scoped to the existing `futseyis-projects/homepage` project/team, and save it as the GitHub Actions **`github-pages` environment** secret `VERCEL_TOKEN` (not a Vercel project environment variable). Do not paste the token into the repository or this document. The project IDs already appear in the workflow; only the secret is required. Keep `main` as the permitted deployment branch and require approval if desired. The preflight step fails before any publishing if the token is absent. Do **not** merge the pipeline change until this secret is configured and staging deployment is ready to validate. Vercel CLI is pinned to a reviewed version in the workflow. The website does not need Vercel's former `GITHUB_TOKEN` after activation. Because Pages and Vercel are separate platforms, their domain updates cannot be atomic; if a publication step fails, the workflow fails rather than publishing any new contribution snapshot from an independent source.

Recent Open Contributions is a **display name**, not a 365-day data cutoff. With `GITHUB_TOKEN`, the build queries GitHub's official GraphQL `contributionsCollection.contributionYears` and reads each active calendar year in API-safe intervals. GitHub-attributed commits, opened pull requests and issues, submitted reviews, and original repository creations (not Fork creations) are grouped by repository, limited to publicly visible repositories, and sorted by the user's latest qualifying contribution timestamp. Each repository appears once. The only deliberate exclusions are `FuTseYi/futseyi.github.io` and `FuTseYi/FuTseYi`. There is no historical age or displayed-repository count cap; the homepage initially shows three entries, then each **Show more** reveals the next incomplete calendar year of repository activity (skipping empty years). **Show less** restores the initial three. A Fork is not included merely because it was created, but qualifying commits, PRs, issues or reviews remain eligible on any public repository, including a Fork.

This uses GitHub's **official contribution criteria**, not a complete event log: ordinary comments, discussions and unmerged branch commits may not count. The GraphQL API limits repositories per category, so overfull periods are recursively split rather than silently truncated. The generated `_site/contributions.json` is a local build artifact, not a separately maintained database. Both hosting platforms receive the **same verified build output**, so their contribution data cannot diverge due to different API credentials. Production `--refresh-activity` builds require `GITHUB_TOKEN` and **fail instead of publishing an empty or incomplete result** when GitHub API queries fail. A local build without credentials can reuse a valid local snapshot or keep the homepage's GitHub activity link. Never commit tokens or generated output.

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
