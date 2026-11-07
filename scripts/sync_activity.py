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

ROOT = Path(__file__).resolve().parents[1]
USER = "FuTseYi"
API = "https://api.github.com"
SNAPSHOT = ROOT / "_site/contributions.json"
EXCLUDED_REPOSITORIES = {"futseyi/futseyi.github.io", "futseyi/futseyi"}
START = "<!-- CONTRIBUTIONS:START -->"
END = "<!-- CONTRIBUTIONS:END -->"
SNAPSHOT_ERRORS = (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError, AttributeError)
REPO_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
GRAPHQL = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalRepositoriesWithContributedCommits
      totalRepositoriesWithContributedPullRequests
      totalRepositoriesWithContributedIssues
      totalRepositoriesWithContributedPullRequestReviews
      commitContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner isPrivate isArchived isDisabled }
        contributions(first: 1, orderBy: {field: OCCURRED_AT, direction: DESC}) {
          nodes { occurredAt }
        }
      }
      pullRequestContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner isPrivate isArchived isDisabled }
        contributions(first: 1, orderBy: {field: OCCURRED_AT, direction: DESC}) {
          nodes { occurredAt }
        }
      }
      issueContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner isPrivate isArchived isDisabled }
        contributions(first: 1, orderBy: {field: OCCURRED_AT, direction: DESC}) {
          nodes { occurredAt }
        }
      }
      pullRequestReviewContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner isPrivate isArchived isDisabled }
        contributions(first: 1, orderBy: {field: OCCURRED_AT, direction: DESC}) {
          nodes { occurredAt }
        }
      }
    }
  }
}
"""
KINDS = (
    ("commitContributionsByRepository", "totalRepositoriesWithContributedCommits", "Commit"),
    ("pullRequestContributionsByRepository", "totalRepositoriesWithContributedPullRequests", "Pull request"),
    ("issueContributionsByRepository", "totalRepositoriesWithContributedIssues", "Issue"),
    ("pullRequestReviewContributionsByRepository",
     "totalRepositoriesWithContributedPullRequestReviews", "Review"),
)


def fetch(url, payload=None, authenticated=True):
    """GitHub JSON transport; token never enters generated assets."""
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "FuTseYi-homepage", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN")
    if authenticated and token and url.startswith(API + "/"):
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=20) as response:
            return json.load(response)
    except HTTPError as error:
        # Log only the endpoint and HTTP code, never the request credentials.
        if error.code != 403:  # A public metadata lookup may recover anonymously.
            print(f"::warning::GitHub API {url.split('?', 1)[0].removeprefix(API)} returned HTTP {error.code}")
        raise


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
    """Keep one latest verified personal contribution per repository, with no age or count cap."""
    now = now or datetime.now(timezone.utc)
    by_name = {}
    for group in groups:
        for entry in group:
            name = entry.get("name")
            if not valid_name(name):
                continue
            date = timestamp(entry["date"])
            if date > now:
                continue
            key = name.lower()
            if key not in by_name or timestamp(by_name[key]["date"]) < date:
                by_name[key] = dict(entry)
    return sorted(by_name.values(), key=lambda e: (timestamp(e["date"]), e["name"].lower()),
                  reverse=True)


def annual_windows(start, end):
    """Cover account lifetime with disjoint, <= one-year GraphQL windows."""
    for year in range(start.year, end.year + 1):
        left = max(start, datetime(year, 1, 1, tzinfo=timezone.utc))
        right = min(end, datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1))
        if left <= right:
            yield left, right


def graphql_window(start, end):
    response = fetch(API + "/graphql", {"query": GRAPHQL,
                     "variables": {"login": USER, "from": start.isoformat(), "to": end.isoformat()}})
    if response.get("errors"):
        raise ValueError("GitHub GraphQL: " + response["errors"][0].get("message", "query failed"))
    collection = response["data"]["user"]["contributionsCollection"]
    rows = []
    for field, total, activity in KINDS:
        groups = collection[field]
        if collection[total] > len(groups):
            # Distinct repositories per window may exceed the GraphQL maxRepositories cap.
            if (end - start) < timedelta(days=1):
                raise ValueError("GitHub GraphQL repository coverage exceeds daily capacity")
            middle = start + (end - start) / 2
            return graphql_window(start, middle) + graphql_window(middle + timedelta(seconds=1), end)
        for group in groups:
            repo = group["repository"]
            if repo["isPrivate"] or repo["isArchived"] or repo["isDisabled"]:
                continue
            nodes = group["contributions"]["nodes"]
            if nodes:
                entry = candidate(repo["nameWithOwner"], nodes[0]["occurredAt"], activity)
                if entry:
                    rows.append(entry)
    return rows


def search(kind, start, end):
    """Date-partition GitHub Search so its 1,000-result limit never silently truncates."""
    if kind == "prs":
        query, endpoint, sort = f"is:pr author:{USER}", "/search/issues", "created"
    elif kind == "comments":
        query, endpoint, sort = f"commenter:{USER}", "/search/issues", "created"
    else:
        query, endpoint, sort = f"author:{USER}", "/search/commits", "committer-date"
    def request(left, right):
        after, before = left.date().isoformat(), right.date().isoformat()
        clause = "committer-date" if kind == "commits" else "created"
        q = f"{query} {clause}:{after}..{before}"
        params = urlencode({"q": q, "sort": sort, "order": "desc", "per_page": 100, "page": 1})
        first = fetch(API + endpoint + "?" + params)
        if first.get("incomplete_results"):
            raise ValueError("Incomplete GitHub Search index")
        if first["total_count"] > 1000:
            if after == before:
                raise ValueError("GitHub Search exceeded 1,000 results in one day")
            midpoint = left.date() + timedelta(days=(right.date() - left.date()).days // 2)
            pivot = datetime(midpoint.year, midpoint.month, midpoint.day, tzinfo=timezone.utc)
            return request(left, pivot) + request(pivot + timedelta(days=1), right)
        items = list(first["items"])
        for page in range(2, (first["total_count"] + 99) // 100 + 1):
            params = urlencode({"q": q, "sort": sort, "order": "desc", "per_page": 100, "page": page})
            result = fetch(API + endpoint + "?" + params)
            if result.get("incomplete_results"):
                raise ValueError("Incomplete GitHub Search index")
            items.extend(result["items"])
        return items
    return request(start, end)


def pages(url, authenticated=False):
    """Walk public REST collections without silently dropping later pages."""
    for page in range(1, 101):
        items = fetch(url + ("&" if "?" in url else "?") +
                      urlencode({"per_page": 100, "page": page}), authenticated=authenticated)
        yield from items
        if len(items) < 100:
            return
    raise ValueError("GitHub REST pagination exceeded 10,000 items")


def inspect_pr_commits(pr):
    """Find personal commits in PR heads, including unmerged contributions on branches."""
    repo_name = pr["repository_url"].removeprefix(API + "/repos/")
    if not valid_name(repo_name):
        return []
    rows = []
    url = API + "/repos/" + repo_name + "/pulls/" + str(pr["number"]) + "/commits"
    try:
        for commit in pages(url, authenticated=repo_name.split("/")[0].lower() == USER.lower()):
            if (commit.get("author") or {}).get("login", "").lower() != USER.lower():
                continue
            date = (commit.get("commit") or {}).get("author", {}).get("date")
            if date:
                entry = candidate(repo_name, date, "Commit")
                if entry:
                    rows.append(entry)
    except HTTPError as error:
        if error.code != 404:
            raise
    return rows


def comment_contributions(item):
    """Never treat an issue's updated_at (which anyone can change) as personal activity."""
    repo_name = item["repository_url"].removeprefix(API + "/repos/")
    if not valid_name(repo_name):
        return []
    number = item["number"]
    urls = [API + "/repos/" + repo_name + "/issues/" + str(number) + "/comments"]
    if "pull_request" in item:
        urls.append(API + "/repos/" + repo_name + "/pulls/" + str(number) + "/comments")
    rows = []
    try:
        for url in urls:
            for comment in pages(url, authenticated=repo_name.split("/")[0].lower() == USER.lower()):
                if (comment.get("user") or {}).get("login", "").lower() == USER.lower():
                    entry = candidate(repo_name, comment["created_at"], "Comment")
                    if entry:
                        rows.append(entry)
    except HTTPError as error:
        if error.code != 404:
            raise
    return rows


def discover(now):
    created = timestamp(fetch(API + "/users/" + USER)["created_at"])
    windows = list(annual_windows(created, now))
    commits = []
    # GitHub GraphQL covers attributed commits, authored PRs/issues and submitted reviews.
    if os.environ.get("GITHUB_TOKEN"):
        for start, end in windows:
            commits.extend(graphql_window(start, end))
    else:
        print("::warning::GITHUB_TOKEN missing: review and issue contribution history may be incomplete.")
        for start, end in windows:
            for item in search("commits", start, end):
                if (item.get("author") or {}).get("login", "").lower() == USER.lower():
                    entry = candidate(item["repository"]["full_name"],
                                      item["commit"]["author"]["date"], "Commit")
                    if entry:
                        commits.append(entry)
    for start, end in windows:
        for pr in search("prs", start, end):
            if (pr.get("user") or {}).get("login", "").lower() != USER.lower():
                continue
            name = pr["repository_url"].removeprefix(API + "/repos/")
            entry = candidate(name, pr["created_at"], "Pull request")
            if entry:
                commits.append(entry)
                commits.extend(inspect_pr_commits(pr))
        for item in search("comments", start, end):
            commits.extend(comment_contributions(item))
    return commits


def repository_metadata(entries):
    """Verify repository visibility and metadata before publishing."""
    verified = []
    for entry in entries:
        # Tokens scoped to personal repositories may not read other public organizations.
        owner = entry["name"].split("/", 1)[0]
        url = API + "/repos/" + entry["name"]
        try:
            repo = fetch(url, authenticated=owner.lower() == USER.lower())
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
    """Reuse only the build's local snapshot; hosting providers remain independent."""
    try:
        data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        updated = timestamp(data["updated_at"])
        if updated > datetime.now(timezone.utc) or not isinstance(data["entries"], list):
            return None
        render(data)
        return data
    except SNAPSHOT_ERRORS:
        return None


def collect(previous=None, now=None):
    now = now or datetime.now(timezone.utc)
    verified = repository_metadata(merge(discover(now), now=now))
    return {"updated_at": now.isoformat(), "entries": merge(verified, now=now)}


def render(snapshot):
    rows = []
    for entry in snapshot["entries"]:
        name = entry["name"]
        if not valid_name(name):
            raise ValueError("Invalid repository name")
        dt = timestamp(entry["date"])
        description = f'<p>{escape(entry["description"])}</p>' if entry.get("description") else ""
        tags = " · ".join(escape(v) for v in (("Commit" if entry["activity"] == "Code push" else entry["activity"]), entry.get("language", "")) if v)
        rows.append(f'<article class="project-item"><time class="contribution-date" datetime="{dt.date().isoformat()}">{dt:%Y.%m.%d}</time><div>'
                    f'<h3><a href="https://github.com/{name}" target="_blank" rel="noopener noreferrer">'
                    f'{escape(name)} <span class="link-arrow" aria-hidden="true"></span></a></h3>'
                    f'{description}<div class="project-tags"><span>{tags}</span></div></div></article>')
    if not rows:
        rows.append('<p class="section-lead">No verifiable public GitHub contributions available.</p>')
    updated = timestamp(snapshot["updated_at"])
    rows.append(f'<p class="activity-note">Activity snapshot · {updated:%Y.%m.%d} UTC</p>')
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Fetch public GitHub contributions")
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
            print(f"::warning::Public contributions unavailable ({type(error).__name__}: {error}); using local snapshot if present.")
    if snapshot is None:
        SNAPSHOT.unlink(missing_ok=True)
        return
    # Preserve original snapshot timestamp on API failure; never invent new activity.
    snapshot = {**snapshot, "entries": merge(snapshot["entries"])}
    content = render(snapshot)
    html = re.sub(re.escape(START) + r".*?" + re.escape(END),
                  lambda _: START + "\n" + content + "\n" + END, html, flags=re.S)
    page.write_text(html, encoding="utf-8")
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered {len(snapshot['entries'])} public contribution repositories.")


if __name__ == "__main__":
    main()
