"""Build navigation, the home page, and topic and tag pages from article front matter.

Articles are Markdown files under docs/articles/. Adding one does not require
editing mkdocs.yml. Generated pages live only in memory for the build.
"""

from __future__ import annotations

import datetime as dt
import posixpath
import re
import unicodedata
from html import escape
from pathlib import Path
from urllib.parse import urlparse

import yaml
from mkdocs.exceptions import PluginError
from mkdocs.structure.files import File, InclusionLevel

ARTICLE_PREFIX = "articles/"
REQUIRED_META = ("title", "description", "category", "tags", "date", "updated")
REQUIRED_BRANDING = (
    "name",
    "company",
    "description",
    "accent",
    "repository_url",
    "site_url",
)
IMAGE_LINE = re.compile(r"^\s*!\[([^\]]*)\]\(([^)\s]+)")
SOURCES_HEADING = re.compile(r"^## Sources\s*$", re.MULTILINE)
FENCE = re.compile(r"```.*?```", re.DOTALL)
FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)
ACCENT = re.compile(r"^#[0-9A-Fa-f]{6}$")
CAPTION = re.compile(r"^\*(.+)\*$")


class Article:
    def __init__(self, src_uri, title, description, category, tags, date, updated):
        self.src_uri = src_uri
        self.title = title
        self.description = description
        self.category = category
        self.tags = tags
        self.date = date
        self.updated = updated


def on_config(config):
    branding = config.extra.setdefault("branding", {})
    missing = [key for key in REQUIRED_BRANDING if not str(branding.get(key, "")).strip()]
    if missing:
        raise PluginError(
            "extra.branding is missing: " + ", ".join(missing) + ". Edit mkdocs.yml."
        )

    accent = branding["accent"].strip()
    if not ACCENT.match(accent):
        raise PluginError(
            "extra.branding.accent must be a #RRGGBB color. "
            f"Got {accent!r}."
        )

    repository_url = branding["repository_url"].strip().rstrip("/")
    parsed = urlparse(repository_url)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme != "https" or parsed.netloc != "github.com" or len(parts) != 2:
        raise PluginError(
            "extra.branding.repository_url must look like "
            "https://github.com/owner/name."
        )
    owner, repo = parts
    project_url = str(branding.get("project_url") or "").strip()
    if project_url and urlparse(project_url).scheme not in {"http", "https"}:
        raise PluginError("extra.branding.project_url must be an http(s) URL or blank.")

    site_url = branding["site_url"].strip()
    if not site_url.endswith("/"):
        site_url += "/"

    logo = str(branding.get("logo") or "").strip()
    if logo:
        logo_path = Path(config.docs_dir) / logo
        if not logo_path.is_file():
            raise PluginError(f"extra.branding.logo does not exist: docs/{logo}")
        config.theme.logo = logo

    branding.update(
        {
            "name": branding["name"].strip(),
            "company": branding["company"].strip(),
            "description": branding["description"].strip(),
            "accent": accent,
            "accent_light": _mix(accent, (255, 255, 255), 0.28),
            "accent_dark": _mix(accent, (0, 0, 0), 0.22),
            "accent_on_dark": _mix(accent, (255, 255, 255), 0.48),
            "repository_url": repository_url,
            "project_url": project_url,
            "project_configured": bool(project_url),
            "project_href": project_url or f"https://github.com/orgs/{owner}/projects",
            "site_url": site_url,
            "issues_url": f"{repository_url}/issues",
            "curiosity_url": f"{repository_url}/issues/new?template=curiosity.yml",
            "repo_name": f"{owner}/{repo}",
        }
    )
    branding["accent_transparent"] = branding["accent"] + "1f"
    branding["accent_on_dark_transparent"] = branding["accent_on_dark"] + "24"

    config.site_name = branding["name"]
    config.site_description = branding["description"]
    config.site_url = branding["site_url"]
    config.site_author = branding["company"]
    config.repo_url = branding["repository_url"]
    config.repo_name = branding["repo_name"]
    config.copyright = f"{branding['name']} · {branding['company']}"
    return config


def on_files(files, config):
    articles = _load_articles(files, config)
    _validate_slugs(articles)
    catalog = _catalog(articles)
    config.extra["_catalog"] = catalog

    for src_uri, content in _generated_pages(catalog, config.extra["branding"]).items():
        # Tag pages are linked from articles. They are not part of the primary nav.
        inclusion = InclusionLevel.NOT_IN_NAV if src_uri.startswith("tags/") else InclusionLevel.UNDEFINED
        files.append(File.generated(config, src_uri, content=content, inclusion=inclusion))

    config.nav = _navigation(catalog, config.extra["branding"])
    return files


def on_page_markdown(markdown, page, config, files):
    catalog = config.extra.get("_catalog") or {}
    article = catalog.get("by_src", {}).get(page.file.src_uri)
    if article is None:
        return markdown
    header = _article_header(article, catalog)
    footer = _article_footer(article, catalog)
    parts = [header, markdown]
    if footer:
        parts.append(footer)
    return "\n\n".join(parts)


def _load_articles(files, config):
    docs_dir = Path(config.docs_dir).resolve()
    articles = []
    for file in files:
        if not file.is_documentation_page():
            continue
        if not file.src_uri.startswith(ARTICLE_PREFIX):
            continue
        meta, body = _split_front_matter(file.content_string, file.src_uri)
        _validate_meta(meta, file.src_uri)
        _validate_sources(body, file.src_uri)
        _validate_images(body, file.src_uri, docs_dir)
        articles.append(
            Article(
                src_uri=file.src_uri,
                title=str(meta["title"]).strip(),
                description=str(meta["description"]).strip(),
                category=str(meta["category"]).strip(),
                tags=[str(tag).strip() for tag in meta["tags"]],
                date=_as_date(meta["date"], "date", file.src_uri),
                updated=_as_date(meta["updated"], "updated", file.src_uri),
            )
        )
    return articles


def _split_front_matter(text, src_uri):
    match = FRONT_MATTER.match(text)
    if not match:
        raise PluginError(f"{src_uri}: add YAML front matter between --- lines.")
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as error:
        raise PluginError(f"{src_uri}: front matter is not valid YAML ({error}).") from error
    if not isinstance(meta, dict):
        raise PluginError(f"{src_uri}: front matter must be a mapping.")
    return meta, match.group(2)


def _validate_meta(meta, src_uri):
    missing = [key for key in REQUIRED_META if key not in meta or meta[key] in ("", None, [])]
    if missing:
        raise PluginError(
            f"{src_uri}: front matter needs {', '.join(missing)}."
        )
    if not isinstance(meta["title"], str) or not meta["title"].strip():
        raise PluginError(f"{src_uri}: title must be text.")
    if not isinstance(meta["description"], str) or not meta["description"].strip():
        raise PluginError(f"{src_uri}: description must be text.")
    if not isinstance(meta["category"], str) or not meta["category"].strip():
        raise PluginError(f"{src_uri}: category must be a single text value.")
    if not isinstance(meta["tags"], list) or not meta["tags"]:
        raise PluginError(f"{src_uri}: tags must be a non-empty list.")
    for tag in meta["tags"]:
        if not isinstance(tag, str) or not tag.strip():
            raise PluginError(f"{src_uri}: every tag must be text.")


def _as_date(value, field, src_uri):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError:
            pass
    raise PluginError(f"{src_uri}: {field} must be a YYYY-MM-DD date.")


def _validate_sources(body, src_uri):
    headings = list(SOURCES_HEADING.finditer(body))
    if len(headings) != 1:
        raise PluginError(
            f"{src_uri}: end the article with one '## Sources' section. "
            "List every source you actually used, as a live link. Never invent one."
        )
    section = body[headings[0].end() :]
    if re.search(r"^##\s+", section, re.MULTILINE):
        raise PluginError(f"{src_uri}: Sources must be the last section.")
    links = re.findall(r"\[[^\]]+\]\((https?://[^)\s]+)\)", section)
    links += re.findall(r"<(https?://[^>\s]+)>", section)
    if not links:
        raise PluginError(
            f"{src_uri}: Sources must contain at least one live http(s) link."
        )


def _validate_images(body, src_uri, docs_dir):
    scanned = FENCE.sub("", body)
    if re.search(r"!\[[^\]]*\]\s*\[", scanned):
        raise PluginError(
            f"{src_uri}: use inline images, ![alt](path), not reference-style images."
        )
    lines = scanned.splitlines()
    article_dir = (docs_dir / src_uri).parent
    for index, line in enumerate(lines):
        match = IMAGE_LINE.match(line)
        if not match:
            continue
        alt, target = match.group(1).strip(), match.group(2).strip()
        if not alt:
            raise PluginError(f"{src_uri}: give the image alt text: {target}")
        if target.startswith(("http://", "https://")):
            raise PluginError(
                f"{src_uri}: do not hotlink {target}. Save it under "
                "docs/articles/<slug>/imported/ and credit the source in the caption."
            )
        image_path = (article_dir / target).resolve()
        if docs_dir not in image_path.parents or not image_path.is_file():
            raise PluginError(f"{src_uri}: image not found: {target}")
        caption = _next_content_line(lines, index + 1)
        caption_match = CAPTION.match(caption or "")
        if not caption_match:
            raise PluginError(
                f"{src_uri}: put a one-line italic caption directly under {target}."
            )
        caption_text = caption_match.group(1)
        imported = "/imported/" in target.replace("\\", "/")
        if imported and not re.search(r"\[[^\]]+\]\(https?://", caption_text):
            raise PluginError(
                f"{src_uri}: the caption for imported image {target} needs a "
                "live link to the page it came from."
            )
        if not imported and "original" not in caption_text.lower():
            raise PluginError(
                f"{src_uri}: the caption for {target} must say it is original, "
                "so it is not mistaken for official documentation."
            )


def _next_content_line(lines, start):
    for line in lines[start:]:
        if line.strip():
            return line.strip()
    return ""


def _validate_slugs(articles):
    owners = {}
    for article in articles:
        pairs = [(article.category, "category")]
        pairs += [(tag, "tag") for tag in article.tags]
        for label, kind in pairs:
            slug = _slugify(label)
            if not slug:
                raise PluginError(
                    f"{article.src_uri}: {kind} {label!r} does not make a URL slug."
                )
            previous = owners.get(slug)
            if previous and previous != label:
                raise PluginError(
                    f"{previous!r} and {label!r} would share the URL slug '{slug}'."
                )
            owners[slug] = label


def _slugify(value):
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _catalog(articles):
    by_updated = sorted(articles, key=lambda article: (article.updated, article.date, article.title.lower()), reverse=True)
    by_date = sorted(articles, key=lambda article: (article.date, article.title.lower()))
    categories = {}
    tags = {}
    for article in by_updated:
        categories.setdefault(article.category, []).append(article)
        for tag in article.tags:
            tags.setdefault(tag, []).append(article)
    return {
        "articles": articles,
        "by_src": {article.src_uri: article for article in articles},
        "by_updated": by_updated,
        "by_date": by_date,
        "categories": dict(sorted(categories.items(), key=lambda item: item[0].lower())),
        "tags": dict(sorted(tags.items(), key=lambda item: item[0].lower())),
    }


def _generated_pages(catalog, branding):
    pages = {
        "index.md": _home(catalog, branding),
        "all-articles.md": _article_index(catalog),
        "search.md": _search_page(branding),
        "topics/index.md": _topics_index(catalog),
        "tags/index.md": _tags_index(catalog),
    }
    for category, articles in catalog["categories"].items():
        pages[f"topics/{_slugify(category)}.md"] = _term_page(
            "Topic", category, articles, "topics"
        )
    for tag, articles in catalog["tags"].items():
        pages[f"tags/{_slugify(tag)}.md"] = _term_page("Tag", tag, articles, "tags")
    return pages


def _page(title, body, description="", *, omit_title=False):
    meta = {
        "search": {"exclude": True},
        "hide": ["toc"],
    }
    if not omit_title:
        meta["title"] = title
    if description:
        meta["description"] = description
    dumped = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{dumped}\n---\n\n{body.strip()}\n"


def _home(catalog, branding):
    recent = catalog["by_updated"][:8]
    if recent:
        cards = "\n\n".join(_card(article, "index.md") for article in recent)
        recent_block = cards
    else:
        recent_block = "No articles yet. Add one Markdown file under `docs/articles/`."

    if catalog["categories"]:
        topics = "\n".join(
            f"- [{_md(category)}](topics/{_slugify(category)}.md) ({len(articles)})"
            for category, articles in catalog["categories"].items()
        )
    else:
        topics = "Topics appear here when an article names a category."

    project_note = ""
    if not branding["project_configured"]:
        project_note = (
            "\n\nThe GitHub Project link opens the organization's projects page. "
            "A specific board is not configured yet.\n"
        )

    body = f"""
# {_md(branding["name"])}

<p class="notebook-kicker">{escape(branding["company"])}</p>

{escape(branding["description"])}

<div class="notebook-search">
  <input type="search" placeholder="Search articles…" aria-label="Search articles" data-notebook-search>
</div>

<div class="notebook-actions" markdown="1">

[Add a Curiosity]({branding["curiosity_url"]}){{ .md-button .md-button--primary }}
[GitHub Project]({branding["project_href"]}){{ .md-button }}

</div>
{project_note}
## Recent articles

{recent_block}

## Topics

{topics}
"""
    return _page(branding["name"], body, branding["description"], omit_title=True)


def _card(article, from_src):
    tags = " · ".join(
        f"[{_md(tag)}]({_rel(from_src, f'tags/{_slugify(tag)}.md')})"
        for tag in article.tags
    )
    return f"""
<article class="notebook-card" markdown="1">

{_format_date(article.updated)} · [{_md(article.category)}]({_rel(from_src, f"topics/{_slugify(article.category)}.md")})
{{.notebook-card__meta}}

[{_md(article.title)}]({_rel(from_src, article.src_uri)})
{{.notebook-card__title}}

{article.description}

{tags}
{{.notebook-tags}}

</article>
""".strip()


def _article_index(catalog):
    if not catalog["by_updated"]:
        body = "No articles yet."
    else:
        body = "\n\n".join(_card(article, "all-articles.md") for article in catalog["by_updated"])
    return _page("All Articles", body, "Every article in the notebook.")


def _topics_index(catalog):
    if not catalog["categories"]:
        listing = "No topics yet."
    else:
        listing = "\n".join(
            f"- [{_md(category)}]({_slugify(category)}.md) "
            f"({len(articles)} {'article' if len(articles) == 1 else 'articles'})"
            for category, articles in catalog["categories"].items()
        )
    body = f"""
{listing}

Tags are listed on [Tags](../tags/index.md).
"""
    return _page("Topics", body, "Categories named by the articles.")


def _tags_index(catalog):
    if not catalog["tags"]:
        listing = "No tags yet."
    else:
        listing = "\n".join(
            f"- [{_md(tag)}]({_slugify(tag)}.md) ({len(articles)})"
            for tag, articles in catalog["tags"].items()
        )
    return _page("Tags", listing, "Tags named by the articles.")


def _term_page(kind, label, articles, folder):
    cards = "\n\n".join(
        _card(article, f"{folder}/{_slugify(label)}.md") for article in articles
    )
    noun = "article" if len(articles) == 1 else "articles"
    body = f"{len(articles)} {noun}.\n\n{cards}"
    return _page(label, body, f"{kind}: {label}")


def _search_page(branding):
    body = f"""
<div class="notebook-search">
  <input type="search" placeholder="Search articles…" aria-label="Search articles" data-notebook-search>
</div>

Search covers the text of every article. The same search is in the header on every page.
"""
    return _page("Search", body, f"Search {branding['name']}.")


def _navigation(catalog, branding):
    topics = [{"Topics": "topics/index.md"}]
    for category in catalog["categories"]:
        topics.append({category: f"topics/{_slugify(category)}.md"})
    return [
        {"Home": "index.md"},
        {"All Articles": "all-articles.md"},
        {"Topics": topics},
        {"Search": "search.md"},
        {"Add a Curiosity": branding["curiosity_url"]},
        {"GitHub Project": branding["project_href"]},
    ]


def _article_header(article, catalog):
    category = (
        f"[{_md(article.category)}]"
        f"({_rel(article.src_uri, f'topics/{_slugify(article.category)}.md')})"
    )
    if article.updated != article.date:
        when = (
            f"Published {_format_date(article.date)} · "
            f"Updated {_format_date(article.updated)}"
        )
    else:
        when = _format_date(article.date)
    tags = " · ".join(
        f"[{_md(tag)}]({_rel(article.src_uri, f'tags/{_slugify(tag)}.md')})"
        for tag in article.tags
    )
    return f"{when} · {category}\n{{.article-meta}}\n\n{tags}\n{{.notebook-tags}}"


def _article_footer(article, catalog):
    ordered = catalog["by_date"]
    index = ordered.index(article)
    links = []
    if index > 0:
        previous = ordered[index - 1]
        links.append(
            f"[Previous: {_md(previous.title)}]({_rel(article.src_uri, previous.src_uri)})"
        )
    if index + 1 < len(ordered):
        nxt = ordered[index + 1]
        links.append(f"[Next: {_md(nxt.title)}]({_rel(article.src_uri, nxt.src_uri)})")

    related = []
    for other in catalog["by_updated"]:
        if other is article:
            continue
        shares_topic = other.category == article.category
        shares_tag = bool(set(other.tags) & set(article.tags))
        if shares_topic or shares_tag:
            related.append(
                f"[{_md(other.title)}]({_rel(article.src_uri, other.src_uri)})"
            )
        if len(related) == 3:
            break

    blocks = []
    if related:
        blocks.append("Related: " + " · ".join(related) + "\n{.article-related}")
    if links:
        blocks.append(" · ".join(links) + "\n{.article-pager}")
    return "\n\n".join(blocks)


def _rel(from_src, to_src):
    start = posixpath.dirname(from_src)
    return posixpath.relpath(to_src, start or ".")


def _md(value):
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _format_date(value):
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _mix(color, target, amount):
    red, green, blue = _rgb(color)
    return "#{:02x}{:02x}{:02x}".format(
        *[round(channel + (aim - channel) * amount) for channel, aim in zip((red, green, blue), target)]
    )


def _rgb(color):
    return tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))
