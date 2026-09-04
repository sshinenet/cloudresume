# resume/

Résumé sources and the build that turns them into every format handed out.
The site serves exactly one file from here: `dist/Steven-Shine-Resume.pdf`.

## Layout

```
src/<variant>.md     one Markdown source per tailored résumé (the truth)
build.py             renders md, json, txt, html, pdf, jpg, docx, linkedin
linkedin_diff.py     LinkedIn data export vs. a variant: what to paste where
tests/               pytest suite for linkedin_diff.py
theme.css            default look (= themes/modern.css); HTML → PDF/JPG
themes/              alternative looks: classic, editorial, modern
denylist.txt         terms that must never appear; build fails on a hit  (ignored)
dist/                the published PDF, referenced by main.tf   (tracked)
out/<variant>/       build outputs                              (ignored)
assets/              headshot and other non-site images         (ignored)
previous/            older résumés, LinkedIn data exports        (ignored)
```

Only `build.py`, `linkedin_diff.py`, `tests/`, `pytest.ini`, `theme.css`,
`themes/`, `README.md`, `src/general.md`, and `dist/` are tracked.
`denylist.txt` is deliberately ignored: it names the very terms that must
never be published, so it lives only on the build machine. Tailored variants
and LinkedIn exports stay local too.

## Build

```bash
python build.py                      # all variants, all formats
python build.py cloud security       # named variants
python build.py --formats pdf,json   # subset of formats
python build.py --check              # denylist + parse check only
python build.py --publish general    # also copy that PDF to dist/ for the site
python build.py --theme editorial    # use themes/editorial.css; outputs get a -editorial suffix
python build.py --list
```

Themes live in `themes/*.css`; `theme.css` is the default and is the `modern` theme
(chosen 2026-09-04). `classic` is the original layout and `editorial` a serif alternative. The HTML gives each
theme these hooks: `.sec-<section>` on every section, `.entry.first` on the
first entry of a section, `strong.k` / `span.v` inside skill rows, and an
optional `ul.highlights` strip fed by a `highlights:` front-matter line of
pipe-separated facts (a leading number is wrapped in `strong.n`).

Layout rule learned the hard way: keep skill labels inline with their values.
A fixed-width label column reads as two columns to PDF text extractors and
detaches every label from its value.

Needs Python 3.11+ with `playwright`, `python-docx`, `pypdf`, and `Pillow`.
PDF and JPG rendering use whichever Chromium Playwright can launch (Edge, then
Chrome, then its bundled build).

## Source format

Strict Markdown so it stays readable and parses without a real Markdown
library:

```markdown
---
name: Steven Shine
title: shown under the name
headline: LinkedIn headline (≤220 chars)
location: Denver, CO
email: …          phone: …          website: …
linkedin: linkedin.com/in/…         github: github.com/…
variant: short-name                 target: who this one is for
---

## Summary
One or more paragraphs.

## Experience
### Job Title | Employer
Sep 2023 – Present · Denver, CO
- Bullet. Continuation lines start with two spaces.
- **Bold** is the only inline markup.

## Projects
### Project | url.or.subtitle
2023 – 2026
- Bullet.

## Skills
- **Category:** comma, separated, keywords

## Education
### BA, Field | Institution
May 2009
```

Rules: `## ` starts a section; `### ` starts an entry; the first plain line
after an entry heading is `dates · location`; `- ` bullets belong to the
nearest entry, or make the section a list when there is no entry. Sections
named Summary, Experience, Projects, Skills, Education, and Certifications map
onto the JSON Resume schema; any other section still renders in the
human-facing formats.

## Outputs, and who they are for

| Format | Audience |
|---|---|
| `pdf` | People. Printed from the HTML through Chromium, text selectable, metadata set. |
| `docx` | Job portals that insist on Word. |
| `jpg` | Previews, image-only upload boxes. Full page, 2× scale. |
| `html` | Anyone with a browser; the PDF is this page printed. |
| `md` | Humans and agents alike; the canonical copy. |
| `txt` | ATS paste boxes, LLM ingestion, anything that chokes on markup. |
| `json` | JSON Resume v1.0.0: structured fields for parsers and agents. |
| `linkedin` | Paste-ready blocks with character counts against LinkedIn's limits. |

## Keeping LinkedIn in sync

LinkedIn has no self-serve API that writes to a profile (the Profile Edit API
is partner-only), and scripted browser edits break its user agreement. The
sanctioned path is one-way: the résumé is the truth, LinkedIn's own data
export tells us what is currently there, and a diff says what to paste.

1. On LinkedIn: Settings → Data privacy → Get a copy of your data → the
   **larger data archive** option (the whole account). The "specific files"
   list has a "Profile" checkbox, but that yields only `Profile.csv`
   (headline, About, location); Positions, Education, Skills, Certifications
   and Projects come only with the full archive. The first email, the
   "Basic" zip within about ten minutes, already contains every file this
   tool reads; the "Complete" zip a day later adds nothing it uses. LinkedIn
   allows one new request every two hours.
2. Drop it in `previous/` (ignored) and run:

```bash
python linkedin_diff.py previous/Basic_LinkedInDataExport.zip --out out/linkedin-drift.md
python linkedin_diff.py previous/export-folder --variant cloud   # unzipped dir, other variant
```

The folder form also lets you hand-build an export from a copied profile
page while you wait: any subset of `Profile.csv`, `Positions.csv`,
`Education.csv`, `Skills.csv`, `Certifications.csv`, `Projects.csv` with
LinkedIn's column headers. Missing files are reported as not compared.

The report lists only fields that differ, each with LinkedIn's current text
and the exact block to paste with its character count against the field
limit. Cosmetic differences are not drift: bullet glyphs, whitespace,
`Colorado` vs `CO`, and a trailing `United States` are normalised first.
Positions pair by a score (company and start date weigh most, then title
similarity) because LinkedIn titles get rewritten; a year-only résumé date
matches any month in that year. Skills become one tag per top-level comma in
the Skills section with parenthetical detail dropped, and a LinkedIn tag such
as `Windows Server` covers a more specific résumé skill such as `Windows Server
2012 R2–2025`. The denylist tells the diff which
LinkedIn employer is the anonymised current one, so that company name is
never reported as a difference, and any denylisted term found in a LinkedIn
free-text field is flagged under **Privacy**. Every term is redacted from the
report itself, so the report is safe to keep anywhere. Exit code 1 means
drift, 0 means clean, 2 means bad input. Tests: `python -m pytest`.

## Privacy guard

`denylist.txt` names the current employer, its domains, hostnames, ticket
prefixes, and industry tells. `build.py` scans the source and every text
rendering before it writes a byte. A hit aborts the whole build. Add a term
there the moment it should never be published; do not rely on remembering.
