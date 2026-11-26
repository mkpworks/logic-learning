# Music Production Notebook

A public, searchable notebook of music-production notes. Articles are Markdown files. [MkDocs](https://www.mkdocs.org/) and [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) turn them into the site. GitHub Pages hosts it. GitHub Issues collects questions.

The notebook is published by [MKP Works](https://github.com/mkpworks). Names, color, and links live in one place: `extra.branding` in `mkdocs.yml`.

## View the website

After GitHub Pages is enabled, the site is:

<https://mkpworks.github.io/logic-learning/>

Until the first publish, run it locally.

## Run it locally

Python 3.12 is what the publish workflow uses.

```bash
python3 -m pip install -r requirements.txt
python3 -m mkdocs serve
```

Open <http://127.0.0.1:8000>. The dev server redirects to `/logic-learning/`, the same path GitHub Pages will use. Check a production build with:

```bash
python3 -m mkdocs build --strict
```

## Add an article

Create one file, `docs/articles/<slug>.md`. Do not edit the navigation or add category pages. The build reads the front matter and generates the home page, All Articles, Topics, Tags, and search entries.

```yaml
---
title: The question, phrased as a reader would ask it
description: One or two sentences.
category: Spatial Audio and Dolby Atmos
tags:
  - Logic Pro
date: 2026-11-26
updated: 2026-11-26
---
```

Use the real dates. `category` is a single label. `tags` is a list. A new label becomes a new topic or tag page on the next build. Empty topics are not created.

End every article with a `## Sources` section. List each document you used as a live link. Do not invent sources. The strict build rejects an article without that section.

```markdown
## Sources

- [Overview of the Logic Pro for Mac 3D Object Panner](https://support.apple.com/guide/logicpro/lgcp4492e120/mac)
```

Put original diagrams in `docs/articles/<slug>/images/`. Put images saved from a documentation site in `docs/articles/<slug>/imported/`. Every image needs alt text and a one-line italic caption underneath. Original captions say the drawing is original. Imported captions link to the page the file came from. Details and the licensing note are in `AGENTS.md`.

A logo, if you add one, goes in `docs/assets/` and is set with `extra.branding.logo`.

## Change the branding

Edit `extra.branding` in `mkdocs.yml`:

| Key | Role |
| --- | --- |
| `name` | Site name |
| `company` | Parent name, shown on the home page and in the footer |
| `description` | Short description on the home page |
| `logo` | Path under `docs/`, or blank |
| `accent` | Header and link color, as `#RRGGBB` |
| `repository_url` | This GitHub repository |
| `project_url` | A GitHub Project URL, or blank |
| `site_url` | Public site URL, with a trailing slash |

Leave `project_url` blank until a project exists. The GitHub Project link then opens the organization's projects page, and the home page says that no board is configured.

No GitHub Project was found for the `mkpworks` organization or for `logic-learning` on 26 November 2026.

## Capture a curiosity

Use **Add a Curiosity** in the site header, or open:

<https://github.com/mkpworks/logic-learning/issues/new?template=curiosity.yml>

The form asks for a title, the question or idea, and optional context. Issues are public. Sending one does not start research.

Open issues: <https://github.com/mkpworks/logic-learning/issues>

The form applies a `curiosity` label. Create that label in the repository if you want it to stick. GitHub ignores a label that does not exist yet.

## GitHub Project

The site's GitHub Project link uses `extra.branding.project_url`. Set that when you have a board.

To drop new repository issues onto a project automatically, use GitHub's own workflow. Nothing in this repo does it.

1. Open the project.
2. Open the project menu and choose **Workflows**.
3. Open **Auto-add to project**.
4. Limit it to this repository's issues, then turn the workflow on.

GitHub's current description of that workflow: [Adding items automatically](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/adding-items-automatically).

This site does not copy the project board and does not create a project for you.

## Ask an agent to write an article

`AGENTS.md` is the standing brief. A request can be as small as:

```text
Research whether Logic Pro can use an LFO to automate three-dimensional object panning. Write an article for this notebook explaining the available methods, their limitations, and how to try them.
```

Or, with no research yet:

```text
Add a curiosity about using an iPhone as a spatial audio controller. Don't research it yet.
```

The agent adds or edits one Markdown article, keeps Sources honest, and runs `python3 -m mkdocs build --strict`.

## Publish

`.github/workflows/pages.yml` builds the site on every pull request, and builds and deploys it when `main` changes. The articles stay Markdown either way. Material for MkDocs 9.8, the theme this site uses, prints an end-of-life notice dated May 2027. That notice does not affect the build.

GitHub Pages is not on for this repository yet. One setting has to be changed by hand:

1. Open **Settings → Pages** for `mkpworks/logic-learning`.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.

The first successful run on `main` publishes <https://mkpworks.github.io/logic-learning/>. If the organization blocks Pages or Actions, an owner has to allow them before that URL will answer.

## What this is not

There is no account system, database, course, progress tracking, or automatic research when an issue is filed. The articles are the archive.
