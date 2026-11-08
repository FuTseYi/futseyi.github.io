#!/usr/bin/env python3
"""Render GitHub's official public contribution history into the static homepage."""

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
USER = "FuTseYi"
API = "https://api.github.com/graphql"
SNAPSHOT = ROOT / "_site/contributions.json"
SOURCE_SNAPSHOT = ROOT / "contributions.json"
EXCLUDED_REPOSITORIES = {"futseyi/futseyi.github.io", "futseyi/futseyi"}
START = "<!-- CONTRIBUTIONS:START -->"
END = "<!-- CONTRIBUTIONS:END -->"
REPO_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")

YEARS_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection { contributionYears }
  }
}
"""

# The latest contribution per repository and category is enough for the existing cards.
# GitHub bounds the number of repositories per collection; incomplete windows are split.
COLLECTION_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalRepositoriesWithContributedCommits
      totalRepositoriesWithContributedPullRequests
      totalRepositoriesWithContributedIssues
      totalRepositoriesWithContributedPullRequestReviews
      totalRepositoryContributions
      commitContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner visibility description primaryLanguage { name } }
        contributions(first: 1, orderBy: {field: OCCURRED_AT, direction: DESC}) {
          nodes { occurredAt }
        }
      }
      pullRequestContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner visibility description primaryLanguage { name } }
        contributions(first: 1, orderBy: {direction: DESC}) {
          nodes { occurredAt }
        }
      }
      issueContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner visibility description primaryLanguage { name } }
        contributions(first: 1, orderBy: {direction: DESC}) {
          nodes { occurredAt }
        }
      }
      pullRequestReviewContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner visibility description primaryLanguage { name } }
        contributions(first: 1, orderBy: {direction: DESC}) {
          nodes { occurredAt }
        }
      }
      repositoryContributions(first: 100) {
        nodes {
          occurredAt
          repository { nameWithOwner visibility isFork description primaryLanguage { name } }
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


def query(document, **variables):
    """One authenticated GitHub API transport; no token in published assets."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN is required for official contribution history")
    request = Request(API, data=json.dumps({"query": document, "variables": variables}).encode(),
                      headers={"Authorization": "Bearer " + token,
                               "Content-Type": "application/json",
                               "Accept": "application/vnd.github+json",
                               "User-Agent": "FuTseYi-homepage"})
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get("errors"):
        raise ValueError("GitHub GraphQL: " + result["errors"][0].get("message", "query failed"))
    return result["data"]["user"]


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timezone is required")
    return result.astimezone(timezone.utc)


def valid_name(name):
    return (isinstance(name, str) and bool(REPO_NAME.fullmatch(name))
            and name.lower() not in EXCLUDED_REPOSITORIES)


def contribution(repo, date, activity):
    if not repo or repo.get("visibility") != "PUBLIC":
        return None
    name = repo.get("nameWithOwner")
    if not valid_name(name):
        return None
    return {"name": name, "date": date, "activity": activity,
            "description": repo.get("description") or "",
            "language": (repo.get("primaryLanguage") or {}).get("name") or ""}


def merge(groups, now=None):
    """One latest personal contribution per repository, with no age or count cap."""
    now = now or datetime.now(timezone.utc)
    by_name = {}
    for entry in groups:
        name = entry.get("name")
        if not valid_name(name):
            continue
        date = timestamp(entry["date"])
        if date > now:
            continue
        key = name.lower()
        if key not in by_name or timestamp(by_name[key]["date"]) < date:
            by_name[key] = dict(entry)
    return sorted(by_name.values(),
                  key=lambda entry: (timestamp(entry["date"]), entry["name"].lower()),
                  reverse=True)


def windows(year, now):
    """A calendar year may be 366 days; split it into <=365-day API windows."""
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    finish = min(datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1), now)
    while start <= finish:
        end = min(start + timedelta(days=365) - timedelta(seconds=1), finish)
        yield start, end
        start = end + timedelta(seconds=1)


def collection(start, end):
    data = query(COLLECTION_QUERY, login=USER, **{"from": start.isoformat(), "to": end.isoformat()})
    rows = data["contributionsCollection"]
    # Do not mistake the API's repository cap for the user's lifetime total.
    overflow = any(rows[total] > len(rows[field]) for field, total, _ in KINDS)
    overflow |= rows["totalRepositoryContributions"] > len(rows["repositoryContributions"]["nodes"])
    if overflow:
        if end - start < timedelta(days=1):
            raise ValueError("GitHub contribution repository limit exceeded within one day")
        midpoint = start + (end - start) / 2
        return collection(start, midpoint) + collection(midpoint + timedelta(seconds=1), end)

    entries = []
    for field, _, label in KINDS:
        for group in rows[field]:
            nodes = group["contributions"]["nodes"]
            if nodes:
                entry = contribution(group["repository"], nodes[0]["occurredAt"], label)
                if entry:
                    entries.append(entry)
    for node in rows["repositoryContributions"]["nodes"]:
        if node and not node["repository"]["isFork"]:
            entry = contribution(node["repository"], node["occurredAt"], "Repository")
            if entry:
                entries.append(entry)
    return entries


def collect(now=None):
    now = now or datetime.now(timezone.utc)
    user = query(YEARS_QUERY, login=USER)
    years = sorted(set(user["contributionsCollection"]["contributionYears"]))
    entries = []
    for year in years:
        if year <= now.year:
            for start, end in windows(year, now):
                entries.extend(collection(start, end))
    return {"updated_at": now.isoformat(), "entries": merge(entries, now)}


def render(snapshot):
    rows = []
    for entry in snapshot["entries"]:
        name = entry["name"]
        if not valid_name(name):
            raise ValueError("Invalid repository name")
        dt = timestamp(entry["date"])
        description = f'<p>{escape(entry["description"])}</p>' if entry.get("description") else ""
        label = "Commit" if entry["activity"] == "Code push" else entry["activity"]
        tags = " · ".join(escape(value) for value in (label, entry.get("language", "")) if value)
        rows.append(f'<article class="project-item"><time class="contribution-date" datetime="{dt.date().isoformat()}">{dt:%Y.%m.%d}</time><div>'
                    f'<h3><a href="https://github.com/{name}" target="_blank" rel="noopener noreferrer">'
                    f'{escape(name)} <span class="link-arrow" aria-hidden="true"></span></a></h3>'
                    f'{description}<div class="project-tags"><span>{tags}</span></div></div></article>')
    if not rows:
        rows.append('<p class="section-lead">No verifiable public GitHub contributions available.</p>')
    updated = timestamp(snapshot["updated_at"])
    rows.append(f'<p class="activity-note">Activity snapshot · {updated:%Y.%m.%d} UTC</p>')
    return "\n".join(rows)


def load_snapshot():
    """Read an existing local snapshot, never another provider's website."""
    try:
        data = json.loads(SOURCE_SNAPSHOT.read_text(encoding="utf-8"))
        if timestamp(data["updated_at"]) > datetime.now(timezone.utc):
            return None
        if not isinstance(data["entries"], list) or not data["entries"]:
            return None
        render(data)
        return data
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None



def write_source():
    """Refresh the tracked canonical snapshot only when contribution content changes."""
    updated = collect()
    if not updated["entries"]:
        raise ValueError("GitHub returned no qualifying public contributions")
    if SOURCE_SNAPSHOT.is_file():
        old = json.loads(SOURCE_SNAPSHOT.read_text(encoding="utf-8"))
        if old.get("entries") == updated["entries"]:
            print("Contribution source unchanged.")
            return
    SOURCE_SNAPSHOT.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    print(f"Updated contribution source: {len(updated['entries'])} repositories.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-source", action="store_true",
                        help="Update tracked contributions.json via GitHub Actions")
    options = parser.parse_args()
    if options.write_source:
        write_source()
        return

    page = ROOT / "_site/index.html"
    html = page.read_text(encoding="utf-8")
    if html.count(START) != 1 or html.count(END) != 1:
        raise ValueError("Missing or duplicate contributions slot")
    snapshot = load_snapshot()
    if snapshot is None:
        raise ValueError("Missing or invalid tracked contributions.json; run the Actions sync workflow")
    content = render(snapshot)
    html = re.sub(re.escape(START) + r".*?" + re.escape(END),
                  lambda _: START + "\n" + content + "\n" + END, html, flags=re.S)
    page.write_text(html, encoding="utf-8")
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"Rendered {len(snapshot['entries'])} public contribution repositories.")

if __name__ == "__main__":
    main()
