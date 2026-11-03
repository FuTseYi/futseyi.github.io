#!/usr/bin/env python3
"""Generate or verify a deterministic editorial index for blog source articles."""
from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit
from html.parser import HTMLParser
import markdown
from asset_urls import site_url
from build import get_post

ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = "BLOG_INDEX.json"
EXCERPT_LIMIT = 240
HTML_ENTITIES = {
    "nbsp": " ", "amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'",
    "ndash": "–", "mdash": "—", "hellip": "…", "copy": "©", "reg": "®",
    "trade": "™", "lsquo": "‘", "rsquo": "’", "ldquo": "“", "rdquo": "”",
    "middot": "·", "bull": "•", "times": "×", "divide": "÷", "euro": "€",
    "pound": "£", "yen": "¥", "sect": "§", "para": "¶", "deg": "°", "plusmn": "±",
    "micro": "µ",
}
FENCE_RE = re.compile(r"^ {0,3}(\x60{3,}|~{3,})")
SETEXT_RE = re.compile(r"^ {0,3}(?:=+|-+)\s*$")
ATX_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
BLOCK_RE = re.compile(r"^ {0,3}(?:#{1,6}[ \t]+|[-+*]\s+|\d+[.)]\s+|\x60{3,}|~{3,}|\|)")
INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:[^()]|\([^()]*\))*\)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?:[^()]|\([^()]*\))*\)")
CODE_SPAN_RE = re.compile(r"\x60+([^\x60]+?)\x60+")
ENTITY_RE = re.compile(r"&([a-z]+);", re.IGNORECASE)


def _decode_entities(value: str) -> str:
    value = re.sub(r"&#x([0-9a-f]+);", lambda match: chr(int(match.group(1), 16)), value, flags=re.I)
    value = re.sub(r"&#(\d+);", lambda match: chr(int(match.group(1))), value)
    return ENTITY_RE.sub(lambda match: HTML_ENTITIES.get(match.group(1).lower(), match.group(0)), value)


def _plain_text(value: str, *, heading: bool = False) -> str:
    """Convert a Markdown inline fragment to stable plain text for editorial discovery."""
    value = IMAGE_RE.sub("", value)
    value = INLINE_LINK_RE.sub(r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", value)
    value = re.sub(r"\[\^[^\]]+\]", "", value)
    value = re.sub(r"<(https?://[^>]+)>", r"\1", value)
    value = CODE_SPAN_RE.sub(r"\1", value)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[*_~]{1,3}", "", value)
    value = re.sub(r"\\([\\\x60*{}\[\]()#+\-.!_>])", r"\1", value)
    if heading:
        value = re.sub(r"\s+\{(?=[#.])[^}]*\}\s*$", "", value)
    value = _decode_entities(value)
    value = re.sub(r"[\u200b-\u200d\ufeff]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _fence(line: str):
    return FENCE_RE.match(line)


def _is_setext(lines: list[str], index: int) -> bool:
    return index + 1 < len(lines) and bool(lines[index].strip()) and bool(SETEXT_RE.match(lines[index + 1]))


def extract_headings(source: str) -> list[dict[str, str | int]]:
    """Extract actual Markdown heading levels and plain-text titles, excluding code fences."""
    lines = source.replace("\r", "").split("\n")
    headings = []
    fence_char = None
    fence_size = 0
    for index, line in enumerate(lines):
        marker = _fence(line)
        if marker:
            token = marker.group(1)
            if fence_char is None:
                fence_char, fence_size = token[0], len(token)
            elif token[0] == fence_char and len(token) >= fence_size:
                fence_char, fence_size = None, 0
            continue
        if fence_char is not None:
            continue
        normalized = re.sub(r"^ {0,3}(?:>\s*)+", "", line)
        heading = ATX_RE.match(normalized)
        if heading:
            title = _plain_text(heading.group(2), heading=True)
            if title:
                headings.append({"level": len(heading.group(1)), "title": title})
            continue
        if _is_setext(lines, index):
            title = _plain_text(re.sub(r"^ {0,3}>\s?", "", line), heading=True)
            if title:
                level = 1 if lines[index + 1].strip().startswith("=") else 2
                headings.append({"level": level, "title": title})
    return headings


def extract_excerpt(source: str, limit: int = EXCERPT_LIMIT) -> str:
    """Extract the first meaningful prose paragraph, excluding structural and code blocks."""
    lines = source.replace("\r", "").split("\n")
    excerpt = ""
    fence_char = None
    fence_size = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        marker = _fence(line)
        if marker:
            token = marker.group(1)
            if fence_char is None:
                fence_char, fence_size = token[0], len(token)
            elif token[0] == fence_char and len(token) >= fence_size:
                fence_char, fence_size = None, 0
            index += 1
            continue
        if fence_char is not None or not line.strip():
            index += 1
            continue
        if _is_setext(lines, index):
            index += 2
            continue
        if (re.match(r"^ {0,3}#{1,6}[ \t]+", line) or re.match(r"^ {0,3}(?:[-*_]\s*){3,}$", line)
                or re.match(r"^ {0,3}(?:[-+*]|\d+[.)])\s+", line)
                or re.match(r"^ {0,3}\|", line)
                or re.match(r"^ {0,3}\[[^\]]+\]:", line)):
            index += 1
            continue
        if re.match(r"^ {0,3}<", line) and not re.match(r"^ {0,3}<(?:p|blockquote)\b", line, re.I):
            index += 1
            continue
        block = []
        if re.match(r"^ {0,3}>", line):
            while index < len(lines) and re.match(r"^ {0,3}>", lines[index]):
                block.append(re.sub(r"^ {0,3}>+\s?", "", lines[index]))
                index += 1
        else:
            while index < len(lines):
                candidate = lines[index]
                if not candidate.strip() or BLOCK_RE.match(candidate) or re.match(r"^ {0,3}(?:[-*_]\s*){3,}$", candidate):
                    break
                if _is_setext(lines, index):
                    break
                if re.match(r"^ {0,3}<", candidate) and not re.match(r"^ {0,3}<(?:p|blockquote)\b", candidate, re.I):
                    break
                block.append(candidate)
                index += 1
        excerpt = _plain_text(" ".join(block))
        if excerpt:
            break
    characters = list(excerpt)
    if len(characters) > limit:
        shortened = "".join(characters[:limit])
        if " " in shortened:
            shortened = shortened.rsplit(" ", 1)[0]
        excerpt = shortened.rstrip(" ,;:") + "…"
    return excerpt


class _ArticleHTMLParser(HTMLParser):
    """Collect explicit article links from rendered Markdown, excluding code examples."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("pre", "script", "style"):
            self._ignored_depth += 1
        elif tag == "a" and self._ignored_depth == 0:
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag in ("pre", "script", "style") and self._ignored_depth:
            self._ignored_depth -= 1


def extract_internal_links(source: str, slug: str, known_slugs: set[str], origin: str) -> list[str]:
    """Record only explicit rendered links to existing articles on this site."""
    parser = _ArticleHTMLParser()
    parser.feed(markdown.markdown(source, extensions=["extra"]))
    allowed_host = urlsplit(origin).netloc.casefold()
    targets = set()
    for destination in parser.links:
        parsed = urlsplit(destination)
        if parsed.scheme and parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc and parsed.netloc.casefold() != allowed_host:
            continue
        path = unquote(parsed.path).strip("/")
        match = re.fullmatch(r"(?:blog/)?([a-z0-9]+(?:-[a-z0-9]+)*)", path)
        if match:
            target = match.group(1)
            if target != slug and target in known_slugs:
                targets.add(target)
    return sorted(targets)


def build_index(root: Path = ROOT) -> dict:
    """Build the complete index from Markdown source files."""
    records = []
    for path in sorted((root / "posts").glob("*/index.md")):
        slug = path.parent.name
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError(f"{path}: invalid article slug")
        meta, body = get_post(path)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["date"]):
            raise ValueError(f"{path}: date must use YYYY-MM-DD")
        date.fromisoformat(meta["date"])
        tags = list(dict.fromkeys(tag.strip() for tag in meta.get("tags", "").split(",") if tag.strip()))
        records.append({
            "slug": slug,
            "title": meta["title"],
            "date": meta["date"],
            "tags": tags,
            "path": path.relative_to(root).as_posix(),
            "excerpt": extract_excerpt(body),
            "headings": extract_headings(body),
            "_body": body,
        })
    records.sort(key=lambda item: (item["date"], item["slug"]), reverse=True)
    known_slugs = {item["slug"] for item in records}
    origin = site_url(root)
    articles = []
    tag_articles: dict[str, list[str]] = {}
    for item in records:
        article = {key: value for key, value in item.items() if key != "_body"}
        article["internal_links"] = extract_internal_links(item["_body"], item["slug"], known_slugs, origin)
        articles.append(article)
        for tag in item["tags"]:
            tag_articles.setdefault(tag, []).append(item["slug"])
    tags = [
        {"name": name, "count": len(slugs), "articles": slugs}
        for name, slugs in sorted(
            tag_articles.items(),
            key=lambda pair: (-len(pair[1]), pair[0].casefold(), pair[0]),
        )
    ]
    return {
        "schema_version": 2,
        "generator": ".github/scripts/blog_index.py",
        "articles": articles,
        "tags": tags,
    }


def render_index(root: Path = ROOT) -> str:
    return json.dumps(build_index(root), ensure_ascii=False, indent=2) + "\n"


def write_index(root: Path = ROOT) -> Path:
    destination = root / INDEX_PATH
    destination.write_text(render_index(root), encoding="utf-8")
    return destination


def check_index(root: Path = ROOT) -> None:
    destination = root / INDEX_PATH
    if not destination.is_file():
        raise ValueError(f"Missing {INDEX_PATH}; run python .github/scripts/blog_index.py --write")
    try:
        actual = json.loads(destination.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{INDEX_PATH} contains invalid JSON: {error}") from error
    expected = build_index(root)
    if actual == expected:
        return
    actual_articles = {
        item.get("slug"): item
        for item in actual.get("articles", [])
        if isinstance(item, dict) and isinstance(item.get("slug"), str)
    } if isinstance(actual, dict) and isinstance(actual.get("articles"), list) else {}
    for article in expected["articles"]:
        current = actual_articles.get(article["slug"])
        if current is None:
            raise ValueError(f"{INDEX_PATH} is out of date: missing article {article['slug']}; regenerate the index")
        for field, value in article.items():
            if current.get(field) != value:
                raise ValueError(
                    f"{INDEX_PATH} is out of date at {article['slug']}.{field}; "
                    f"expected {value!r}, found {current.get(field)!r}. "
                    "Run python .github/scripts/blog_index.py --write"
                )
    if not isinstance(actual, dict) or actual.get("tags") != expected["tags"]:
        raise ValueError(f"{INDEX_PATH} tag taxonomy is out of date; regenerate the index")
    raise ValueError(f"{INDEX_PATH} metadata or formatting is out of date; regenerate the index")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--write", action="store_true", help="Generate BLOG_INDEX.json")
    actions.add_argument("--check", action="store_true", help="Verify BLOG_INDEX.json")
    args = parser.parse_args()
    try:
        if args.write:
            print(f"Generated {write_index().relative_to(ROOT)}")
        else:
            check_index()
            print(f"Verified {INDEX_PATH}")
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
