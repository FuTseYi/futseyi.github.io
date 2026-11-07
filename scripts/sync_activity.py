#!/usr/bin/env python3
"""Build the static, verified public-contribution list. No runtime browser requests."""
import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from site_metadata import site_url

ROOT = Path(__file__).resolve().parents[1]
USER = "FuTseYi"
SITE = site_url(ROOT)
API = "https://api.github.com"
SNAPSHOT = ROOT / "_site/contributions.json"
MAX_REPOSITORIES = 12
WINDOW_DAYS = 365
EXCLUDED_REPOSITORIES = {"futseyi/futseyi.github.io", "futseyi/futseyi"}
START = "<!-- CONTRIBUTIONS:START -->"
END = "<!-- CONTRIBUTIONS:END -->"
SNAPSHOT_ERRORS = (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError, AttributeError)
REPO_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
GRAPHQL = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      commitContributionsByRepository(maxRepositories: 100) {
        repository {
          id nameWithOwner isPrivate isArchived isDisabled
          description primaryLanguage { name }
        }
        contributions(first: 1, orderBy: {field: OCCURRED_AT, direction: DESC}) {
          nodes { occurredAt }
        }
      }
    }
  }
}
"""


def fetch(url, payload=None):
    """GitHub JSON transport; token never enters generated assets."""
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "FuTseYi-homepage", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith(API + "/"):
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    with urlopen(Request(url, data=data, headers=headers), timeout=20) as response:
        return json.load(response)


def cutoff(now):
    return now - timedelta(days=WINDOW_DAYS)


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timezone is required")
    return result.astimezone(timezone.utc)


def valid_name(name):
    return isinstance(name, str) and bool(REPO_NAME.fullmatch(name)) and name.lower() not in EXCLUDED_REPOSITORIES


def candidate(name, date, activity, repo=None):
    if not valid_name(name):
        return None
    return {"name": name, "date": date, "activity": activity,
            "description": (repo or {}).get("description") or "",
            "language": (repo or {}).get("language") or ""}


def merge(*groups, now=None):
    """A bounded, deterministic union; stale contributions are not retained forever."""
    now = now or datetime.now(timezone.utc)
    by_name = {}
    for group in groups:
        for entry in group:
            name = entry.get("name")
            if not valid_name(name):
                continue
            date = timestamp(entry["date"])
            if not cutoff(now) <= date <= now:
                continue
            key = name.lower()
            if key not in by_name or timestamp(by_name[key]["date"]) < date:
                by_name[key] = dict(entry)
    return sorted(by_name.values(), key=lambda e: (timestamp(e["date"]), e["name"].lower()),
                  reverse=True)[:MAX_REPOSITORIES]


def graphql_commits(now):
    """GitHub's own contribution semantics; latest day rather than repo pushed_at."""
    from_date = cutoff(now).isoformat()
    response = fetch(API + "/graphql", {"query": GRAPHQL,
                     "variables": {"login": USER, "from": from_date, "to": now.isoformat()}})
    if response.get("errors"):
        raise ValueError("GitHub GraphQL returned errors")
    groups = response["data"]["user"]["contributionsCollection"]["commitContributionsByRepository"]
    entries = []
    for group in groups:
        repo = group["repository"]
        if repo["isPrivate"] or repo["isArchived"] or repo["isDisabled"]:
            continue
        nodes = group["contributions"]["nodes"]
        if nodes:
            entry = candidate(repo["nameWithOwner"], nodes[0]["occurredAt"], "Code push",
                              {"description": repo.get("description"),
                               "language": (repo.get("primaryLanguage") or {}).get("name")})
            if entry:
                entries.append(entry)
    return entries


def search(kind, now):
    """Search is bounded to a year and paginated; fail rather than silently truncate."""
    after = cutoff(now).date().isoformat()
    if kind == "commits":
        query = f"author:{USER} committer-date:>={after}"
        endpoint = "/search/commits"
        sort = "committer-date"
    else:
        query = f"is:pr author:{USER} draft:false created:>={after}"
        endpoint = "/search/issues"
        sort = "created"
    items = []
    for page in range(1, 11):
        params = urlencode({"q": query, "sort": sort, "order": "desc",
                            "per_page": 100, "page": page})
        result = fetch(API + endpoint + "?" + params)
        if result.get("incomplete_results"):
            raise ValueError("Incomplete GitHub search")
        items.extend(result["items"])
        if len(result["items"]) < 100:
            break
        if page == 10:
            raise ValueError("GitHub search exceeded its 1000-result window")
    return items


def search_commits(now):
    entries = []
    for item in search("commits", now):
        if (item.get("author") or {}).get("login", "").lower() != USER.lower():
            continue
        repo = item["repository"]
        entry = candidate(repo["full_name"], item["commit"]["committer"]["date"], "Code push")
        if entry:
            entries.append(entry)
    return entries


def search_prs(now):
    entries = []
    for item in search("prs", now):
        if (item.get("user") or {}).get("login", "").lower() != USER.lower():
            continue
        entry = candidate(item["repository_url"].removeprefix(API + "/repos/"),
                          item["created_at"], "Pull request")
        if entry:
            entries.append(entry)
    return entries


def repository_metadata(entries):
    """Recheck public visibility and repo identity before publishing or retaining caches."""
    verified = []
    for entry in entries:
        try:
            repo = fetch(API + "/repos/" + entry["name"])
        except HTTPError as error:
            if error.code == 404:
                continue
            raise
        if (repo.get("private") or repo.get("visibility", "public") != "public"
                or repo.get("archived") or repo.get("disabled")):
            continue
        name = repo.get("full_name", entry["name"])
        item = candidate(name, entry["date"], entry["activity"], repo)
        if item:
            verified.append(item)
    return verified


def load_snapshot():
    """Local staging cache first, otherwise current published JSON across Vercel builds."""
    for source in (lambda: SNAPSHOT.read_text(encoding="utf-8"),
                   lambda: json.dumps(fetch(SITE + "/contributions.json"))):
        try:
            data = json.loads(source())
            updated = timestamp(data["updated_at"])
            if updated > datetime.now(timezone.utc) or not isinstance(data["entries"], list):
                continue
            render(data)
            return data
        except SNAPSHOT_ERRORS:
            continue
    return None


def collect(previous=None, now=None):
    now = now or datetime.now(timezone.utc)
    # Without credentials, the REST commit search still works (with narrower rate limits).
    commits = graphql_commits(now) if os.environ.get("GITHUB_TOKEN") else search_commits(now)
    prs = search_prs(now)
    candidates = merge(commits, prs, (previous or {}).get("entries", []), now=now)
    verified = repository_metadata(candidates)
    return {"updated_at": now.isoformat(), "entries": merge(verified, now=now)}


def render(snapshot):
    rows = []
    for entry in snapshot["entries"]:
        name = entry["name"]
        if not valid_name(name):
            raise ValueError("Invalid repository name")
        dt = timestamp(entry["date"])
        description = f'<p>{escape(entry["description"])}</p>' if entry.get("description") else ""
        tags = " · ".join(escape(v) for v in (entry["activity"], entry.get("language", "")) if v)
        rows.append(f'<article class="project-item"><time class="contribution-date" datetime="{dt.date().isoformat()}">{dt:%Y.%m.%d}</time><div>'
                    f'<h3><a href="https://github.com/{name}" target="_blank" rel="noopener noreferrer">'
                    f'{escape(name)} <span class="link-arrow" aria-hidden="true"></span></a></h3>'
                    f'{description}<div class="project-tags"><span>{tags}</span></div></div></article>')
    if not rows:
        rows.append('<p class="section-lead">No recent public code pushes or pull requests in the available activity window.</p>')
    updated = timestamp(snapshot["updated_at"])
    rows.append(f'<p class="activity-note">Activity snapshot · {updated:%Y.%m.%d} UTC</p>')
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Fetch fresh public GitHub activity")
    options = parser.parse_args()
    page = ROOT / "_site/index.html"
    html = page.read_text(encoding="utf-8")
    if html.count(START) != 1 or html.count(END) != 1:
        raise ValueError("Missing or duplicate contributions slot")
    previous = load_snapshot()
    snapshot = previous
    if options.refresh or previous is None:
        try:
            snapshot = collect(previous)
        except SNAPSHOT_ERRORS as error:
            print(f"::warning::Public contributions unavailable ({type(error).__name__}); using last valid snapshot.")
    if snapshot is None:
        SNAPSHOT.unlink(missing_ok=True)
        return
    content = render(snapshot)
    html = re.sub(re.escape(START) + r".*?" + re.escape(END),
                  lambda _: START + "\n" + content + "\n" + END, html, flags=re.S)
    page.write_text(html, encoding="utf-8")
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered {len(snapshot['entries'])} public contribution repositories.")


if __name__ == "__main__":
    main()
