#!/usr/bin/env python
"""Report where a LinkedIn profile has drifted from the résumé source.

LinkedIn has no self-serve API that writes to a profile, so this is the
sanctioned alternative: request "Get a copy of your data" (Settings → Data
privacy), download the zip, and point this script at it. It parses the CSVs,
converts a ``src/<variant>.md`` résumé into the same shape, and prints only the
fields that differ, each paired with the exact text to paste and its character
count against LinkedIn's limit.

Usage:
    python linkedin_diff.py path/to/Complete_LinkedInDataExport.zip
    python linkedin_diff.py path/to/unzipped/dir --variant cloud
    python linkedin_diff.py export.zip --out out/linkedin-drift.md

Exit code 0 means no drift, 1 means drift was reported, 2 means bad input.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from build import SRC, load_denylist  # noqa: F401  (module-level so tests can monkeypatch them)


# --------------------------------------------------------------------------- #
# Comparable model (both sides are converted into this)
# --------------------------------------------------------------------------- #

@dataclass
class Position:
    title: str
    company: str = ""
    location: str = ""
    started: str = ""
    finished: str = ""            # "" means current
    description: str = ""


@dataclass
class Education:
    school: str
    degree: str = ""
    started: str = ""
    finished: str = ""


@dataclass
class Certification:
    name: str
    authority: str = ""


@dataclass
class Project:
    title: str
    description: str = ""
    started: str = ""
    finished: str = ""


@dataclass
class Snapshot:
    headline: str = ""
    about: str = ""
    positions: list[Position] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    certifications: list[Certification] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    present: set[str] = field(default_factory=set)   # sections the source actually covered


ALL_SECTIONS = {"Headline", "About", "Experience", "Education", "Skills", "Certifications", "Projects"}


# --------------------------------------------------------------------------- #
# Reading the LinkedIn export
# --------------------------------------------------------------------------- #

_EXPECTED_HEADERS = {
    "Profile.csv": "Headline",
    "Positions.csv": "Company Name",
    "Education.csv": "School Name",
    "Skills.csv": "Name",
    "Certifications.csv": "Name",
    "Projects.csv": "Title",
}
_FILE_SECTIONS = {
    "Profile.csv": {"Headline", "About"},
    "Positions.csv": {"Experience"},
    "Education.csv": {"Education"},
    "Skills.csv": {"Skills"},
    "Certifications.csv": {"Certifications"},
    "Projects.csv": {"Projects"},
}


def _rows(text: str | None, header_key: str) -> list[dict[str, str]]:
    """Parse one export CSV. Some files carry a 'Notes:' preamble before the header."""
    if not text:
        return []
    text = text.lstrip("﻿")
    lines = text.splitlines(keepends=True)
    start = 0
    for n, line in enumerate(lines):
        if header_key in [c.strip() for c in line.strip().split(",")]:
            start = n
            break
    reader = csv.DictReader(io.StringIO("".join(lines[start:])))
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def _read_files(path: Path) -> dict[str, str]:
    """Return {basename: text} for the export CSVs, from a zip or a directory."""
    path = Path(path)
    wanted = set(_EXPECTED_HEADERS)
    out: dict[str, str] = {}
    if path.is_dir():
        for name in wanted:
            f = path / name
            if f.exists():
                out[name] = f.read_text(encoding="utf-8-sig")
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                base = Path(info.filename).name
                if base in wanted and base not in out:
                    out[base] = zf.read(info).decode("utf-8-sig")
    else:
        raise ValueError(f"{path}: not a directory or a zip file")
    return out


def read_export(path: Path) -> Snapshot:
    files = _read_files(Path(path))
    rows = {name: _rows(files.get(name), key) for name, key in _EXPECTED_HEADERS.items()}

    snap = Snapshot(present=set().union(*(_FILE_SECTIONS[f] for f in files)) if files else set())
    if rows["Profile.csv"]:
        p = rows["Profile.csv"][0]
        snap.headline = p.get("Headline", "")
        snap.about = p.get("Summary", "")
    snap.positions = [
        Position(title=r.get("Title", ""), company=r.get("Company Name", ""),
                 location=r.get("Location", ""), started=r.get("Started On", ""),
                 finished=r.get("Finished On", ""), description=r.get("Description", ""))
        for r in rows["Positions.csv"]]
    snap.education = [
        Education(school=r.get("School Name", ""), degree=r.get("Degree Name", ""),
                  started=r.get("Start Date", ""), finished=r.get("End Date", ""))
        for r in rows["Education.csv"]]
    snap.skills = [r["Name"] for r in rows["Skills.csv"] if r.get("Name")]
    snap.certifications = [
        Certification(name=r.get("Name", ""), authority=r.get("Authority", ""))
        for r in rows["Certifications.csv"]]
    snap.projects = [
        Project(title=r.get("Title", ""), description=r.get("Description", ""),
                started=r.get("Started On", ""), finished=r.get("Finished On", ""))
        for r in rows["Projects.csv"]]
    return snap


# --------------------------------------------------------------------------- #
# Converting the résumé model
# --------------------------------------------------------------------------- #

_DASHES = ("–", "—", "-")


def split_dates(dates: str) -> tuple[str, str]:
    """'Sep 2023 – Present' -> ('Sep 2023', ''); 'May 2009' -> ('', 'May 2009')."""
    s = dates.strip()
    for d in _DASHES:
        if f" {d} " in s:
            a, _, b = s.partition(f" {d} ")
            b = b.strip()
            return a.strip(), "" if b.lower() in ("present", "current", "now") else b
    return "", s


def from_resume(r) -> Snapshot:
    from build import linkedin_about, linkedin_entry_text, linkedin_headline, linkedin_skills

    snap = Snapshot(headline=linkedin_headline(r), about=linkedin_about(r), skills=linkedin_skills(r),
                    present=set(ALL_SECTIONS))
    exp = r.section("Experience")
    for e in (exp.entries if exp else []):
        started, finished = split_dates(e.dates)
        snap.positions.append(Position(title=e.title, company=e.org, location=e.location,
                                       started=started, finished=finished,
                                       description=linkedin_entry_text(e)[0]))
    edu = r.section("Education")
    for e in (edu.entries if edu else []):
        started, finished = split_dates(e.dates)
        snap.education.append(Education(school=e.org, degree=e.title, started=started, finished=finished))
    certs = r.section("Certifications")
    for e in (certs.entries if certs else []):
        snap.certifications.append(Certification(name=e.title, authority=e.org))
    proj = r.section("Projects")
    for e in (proj.entries if proj else []):
        started, finished = split_dates(e.dates)
        snap.projects.append(Project(title=e.title, description=linkedin_entry_text(e, limit=None)[0],
                                     started=started, finished=finished))
    return snap


# --------------------------------------------------------------------------- #
# Normalisation (so cosmetic differences are not reported as drift)
# --------------------------------------------------------------------------- #

_WS = re.compile(r"\s+")
_BULLET_PREFIX = re.compile(r"^(?:[-*·•]|\d+[.)])\s*")
_MONTHS = {m.lower(): m[:3] for m in ("January", "February", "March", "April", "May", "June", "July",
                                      "August", "September", "October", "November", "December")}
_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}
_COUNTRY_NOISE = {"united states", "usa", "us", "united states of america"}


def _key(s: str) -> str:
    return _WS.sub(" ", s).strip().casefold()


def _norm_date(s: str) -> str:
    parts = _WS.sub(" ", s).strip().split(" ")
    return " ".join(_MONTHS.get(p.lower(), p) for p in parts).casefold()


_YEAR = re.compile(r"\b(\d{4})\b")


def _dates_equal(a: str, b: str) -> bool:
    """Equal after normalisation; a year-only date on either side compares by year alone, since
    the résumé is allowed to be coarser than LinkedIn (which always stores a month)."""
    na, nb = _norm_date(a), _norm_date(b)
    if na == nb:
        return True
    ya, yb = _YEAR.search(na), _YEAR.search(nb)
    if not (ya and yb):
        return False
    year_only = na == ya.group(1) or nb == yb.group(1)
    return year_only and ya.group(1) == yb.group(1)


def _ranges_equal(r_start: str, r_end: str, l_start: str, l_end: str) -> bool:
    return _dates_equal(r_start, l_start) and _dates_equal(r_end, l_end)


def _norm_location(s: str) -> str:
    parts = [p.strip() for p in s.split(",") if p.strip()]
    parts = [p for p in parts if p.lower() not in _COUNTRY_NOISE]
    parts = [_STATES.get(p.lower(), p) for p in parts]
    return ", ".join(parts).casefold()


def _norm_text(s: str) -> str:
    lines = []
    for raw in s.replace("\r\n", "\n").split("\n"):
        line = _WS.sub(" ", raw).strip()
        if not line:
            continue
        if _BULLET_PREFIX.match(line):
            line = "• " + _BULLET_PREFIX.sub("", line, count=1)
        lines.append(line)
    return "\n".join(lines)


def _date_range(started: str, finished: str) -> str:
    return f"{started} – {finished or 'Present'}" if started else finished


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #

@dataclass
class Finding:
    section: str          # Privacy | Headline | About | Experience | Projects | Education | Certifications | Skills
    item: str             # which entry, "" for single-valued sections
    field: str            # what differs, e.g. "description", "missing on LinkedIn", "not in résumé"
    linkedin: str = ""    # what LinkedIn has now
    resume: str = ""      # what the résumé says (the text to paste)
    limit: int | None = None


def _pair(left: list, right: list, key, fallback_key=None) -> list[tuple]:
    """Match items across two lists by key, then by fallback_key for leftovers. Returns (l, r) pairs
    with None on whichever side is missing."""
    pairs: list[tuple] = []
    unmatched_r = list(right)
    for l in left:
        hit = next((r for r in unmatched_r if key(r) == key(l)), None)
        if hit is None and fallback_key is not None:
            cands = [r for r in unmatched_r if fallback_key(r) == fallback_key(l)]
            if len(cands) == 1 and sum(1 for x in left if fallback_key(x) == fallback_key(l)) == 1:
                hit = cands[0]
        if hit is not None:
            unmatched_r.remove(hit)
        pairs.append((l, hit))
    pairs.extend((None, r) for r in unmatched_r)
    return pairs


def _hits(text: str, terms: list[str]) -> list[str]:
    low = text.lower()
    return [t for t in terms if t.lower() in low]


_TOKEN = re.compile(r"[a-z0-9]+")


def _similarity(a: str, b: str) -> float:
    """Jaccard overlap of word tokens, 0..1."""
    ta, tb = set(_TOKEN.findall(a.lower())), set(_TOKEN.findall(b.lower()))
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def _position_score(r: Position, l: Position, terms: list[str]) -> int:
    """How likely two positions are the same job. Titles get rewritten on LinkedIn, so company and
    start date carry most of the weight; a match needs one of those two plus something else."""
    company_sim = _similarity(r.company, l.company)
    company = 2 if (_hits(l.company, terms) or company_sim >= 0.5) else 0
    start = 2 if _dates_equal(r.started, l.started) else 0
    if not (company or start):
        return 0
    finished = 1 if _dates_equal(r.finished, l.finished) else 0
    title_sim = _similarity(r.title, l.title)
    title = 3 if _key(r.title) == _key(l.title) else (2 if title_sim >= 0.5 else (1 if title_sim >= 0.34 else 0))
    return company + start + finished + title


def _pair_positions(res: list[Position], li: list[Position], terms: list[str], threshold: int = 3) -> list[tuple]:
    """Greedy best-score pairing. Returns (r, l) with None on whichever side has no partner."""
    scored = sorted(((_position_score(r, l, terms), ri, lj) for ri, r in enumerate(res) for lj, l in enumerate(li)),
                    key=lambda t: (-t[0], t[1], t[2]))
    taken_r: dict[int, int] = {}
    taken_l: set[int] = set()
    for score, ri, lj in scored:
        if score < threshold:
            break
        if ri in taken_r or lj in taken_l:
            continue
        taken_r[ri] = lj
        taken_l.add(lj)
    pairs: list[tuple] = [(r, li[taken_r[ri]] if ri in taken_r else None) for ri, r in enumerate(res)]
    pairs.extend((None, l) for lj, l in enumerate(li) if lj not in taken_l)
    return pairs


def diff(res: Snapshot, li: Snapshot, terms: list[str]) -> list[Finding]:
    """Compare the résumé (truth) against LinkedIn. ``terms`` is the denylist: it identifies which
    LinkedIn company is the anonymised current employer, and flags leaks into free-text fields.
    Sections the export did not include are reported once as 'not in export' and otherwise skipped."""
    out: list[Finding] = []
    lim = {"headline": 220, "about": 2600, "description": 2000}
    have = li.present

    for section in sorted(ALL_SECTIONS - have):
        out.append(Finding(section, "", "not in export"))

    # Privacy first: denylist terms in fields the résumé text gets pasted into. Company Name is
    # exempt, since that is where the real employer legitimately lives on LinkedIn.
    for label, text in [("Headline", li.headline), ("About", li.about),
                        *((f"Experience — {p.title}", p.description) for p in li.positions),
                        *((f"Project — {p.title}", p.description) for p in li.projects)]:
        for t in _hits(text, terms):
            out.append(Finding("Privacy", label, "denylist hit", linkedin=t))

    if "Headline" in have and _key(res.headline) != _key(li.headline):
        out.append(Finding("Headline", "", "text", li.headline, res.headline, lim["headline"]))
    if "About" in have and _norm_text(res.about) != _norm_text(li.about):
        out.append(Finding("About", "", "text", li.about, res.about, lim["about"]))

    def pos_item(p: Position) -> str:
        parts = [p.title, p.company, _date_range(p.started, p.finished), p.location]
        return " · ".join(x for x in parts if x)

    for r, l in (_pair_positions(res.positions, li.positions, terms) if "Experience" in have else []):
        if l is None:
            out.append(Finding("Experience", pos_item(r), "missing on LinkedIn", "", r.description, lim["description"]))
            continue
        if r is None:
            out.append(Finding("Experience", pos_item(l), "not in résumé", l.description, ""))
            continue
        item = pos_item(r)
        if _key(r.title) != _key(l.title):
            out.append(Finding("Experience", item, "title", l.title, r.title))
        anonymised = bool(_hits(l.company, terms))
        if not anonymised and _key(r.company) != _key(l.company):
            out.append(Finding("Experience", item, "company", l.company, r.company))
        if not _ranges_equal(r.started, r.finished, l.started, l.finished):
            out.append(Finding("Experience", item, "dates", _date_range(l.started, l.finished),
                               _date_range(r.started, r.finished)))
        if _norm_location(r.location) != _norm_location(l.location):
            out.append(Finding("Experience", item, "location", l.location, r.location))
        if _norm_text(r.description) != _norm_text(l.description):
            out.append(Finding("Experience", item, "description", l.description, r.description, lim["description"]))

    for r, l in (_pair(res.projects, li.projects, key=lambda p: _key(p.title)) if "Projects" in have else []):
        if l is None:
            out.append(Finding("Projects", r.title, "missing on LinkedIn", "", r.description, lim["description"]))
        elif r is None:
            out.append(Finding("Projects", l.title, "not in résumé", l.description, ""))
        else:
            if not _ranges_equal(r.started, r.finished, l.started, l.finished):
                out.append(Finding("Projects", r.title, "dates", _date_range(l.started, l.finished),
                                   _date_range(r.started, r.finished)))
            if _norm_text(r.description) != _norm_text(l.description):
                out.append(Finding("Projects", r.title, "description", l.description, r.description,
                                   lim["description"]))

    for r, l in (_pair(res.education, li.education, key=lambda e: _key(e.school)) if "Education" in have else []):
        if l is None:
            out.append(Finding("Education", r.school, "missing on LinkedIn", "", r.degree))
        elif r is None:
            out.append(Finding("Education", l.school, "not in résumé", l.degree, ""))
        else:
            if _key(r.degree) != _key(l.degree):
                out.append(Finding("Education", r.school, "degree", l.degree, r.degree))
            if not _dates_equal(r.finished, l.finished):
                out.append(Finding("Education", r.school, "dates", _date_range(l.started, l.finished),
                                   _date_range(r.started, r.finished)))

    for r, l in (_pair(res.certifications, li.certifications, key=lambda c: _key(c.name))
                 if "Certifications" in have else []):
        if l is None:
            out.append(Finding("Certifications", r.name, "missing on LinkedIn", "", r.name))
        elif r is None:
            out.append(Finding("Certifications", l.name, "not in résumé", l.name, ""))

    if "Skills" in have:
        # A LinkedIn tag covers a résumé skill when they match exactly or the résumé skill starts
        # with the tag followed by a version or qualifier ("Windows Server" covers "Windows Server
        # 2012 R2–2025"; "VMware" covers "VMware vSphere/ESXi 8").
        def covers(tag: str, skill: str) -> bool:
            t, s = _key(tag), _key(skill)
            if s == t or (s.startswith(t) and len(s) > len(t) and not s[len(t)].isalnum()):
                return True
            # LinkedIn's canonical names are longer and carry an alias in parentheses:
            # "Transact-SQL (T-SQL)" covers "T-SQL", "Python (Programming Language)" covers
            # "Python", "Cisco Identity Services Engine (ISE)" covers "Cisco ISE".
            st, tt = set(_TOKEN.findall(s)), set(_TOKEN.findall(t))
            return bool(st) and st <= tt

        used_tags: set[str] = set()
        for s in res.skills:
            tag = next((t for t in li.skills if covers(t, s)), None)
            if tag is None:
                out.append(Finding("Skills", s, "missing on LinkedIn", "", s))
            else:
                used_tags.add(_key(tag))
        for t in li.skills:
            if _key(t) not in used_tags:
                out.append(Finding("Skills", t, "not in résumé", t, ""))
    return out


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #

_SECTION_ORDER = ["Privacy", "Headline", "About", "Experience", "Projects", "Education", "Certifications", "Skills"]


def redact(text: str, terms: list[str]) -> str:
    for t in sorted(terms, key=len, reverse=True):
        text = re.sub(re.escape(t), "[redacted]", text, flags=re.IGNORECASE)
    return text


def render_report(findings: list[Finding], terms: list[str], variant: str = "") -> str:
    o = ["# LinkedIn drift report", ""]
    label = f"résumé variant `{variant}`" if variant else "résumé"
    skipped = [f.section for f in findings if f.field == "not in export"]
    findings = [f for f in findings if f.field != "not in export"]
    if not findings:
        o.append(f"No drift: LinkedIn matches the {label}.")
    else:
        o.append(f"{len(findings)} difference(s) between the {label} and the LinkedIn export. "
                 "The résumé is the source of truth; paste the blocks below into LinkedIn.")
    o.append("")
    if skipped:
        o.extend([f"Sections not in export, so not compared: {', '.join(skipped)}.", ""])
    if not findings:
        return redact("\n".join(o) + "\n", terms)

    def fence(text: str) -> list[str]:
        return ["```", text, "```"]

    for section in _SECTION_ORDER:
        fs = [f for f in findings if f.section == section]
        if not fs:
            continue
        o.extend([f"## {section}", ""])
        if section == "Privacy":
            for f in fs:
                o.append(f"- **{f.item}** on LinkedIn contains a denylisted term: `{f.linkedin}`. Remove it.")
            o.append("")
            continue
        if section == "Skills":
            missing = [f.resume for f in fs if f.field == "missing on LinkedIn"]
            extra = [f.linkedin for f in fs if f.field == "not in résumé"]
            if missing:
                o.extend([f"Add on LinkedIn ({len(missing)}; LinkedIn allows 100 total):", "",
                          *fence("\n".join(missing)), ""])
            if extra:
                o.extend([f"On LinkedIn but not in the résumé ({len(extra)}), keep or remove:", "",
                          *fence("\n".join(extra)), ""])
            continue
        for f in fs:
            head = f"### {f.item} — {f.field}" if f.item else f"### {f.field}"
            o.extend([head, ""])
            if f.field == "not in résumé":
                o.append("Exists on LinkedIn only. Add it to the résumé source or remove it from LinkedIn.")
                if f.linkedin:
                    o.extend(["", *fence(f.linkedin)])
                o.append("")
                continue
            if f.linkedin:
                o.extend(["LinkedIn now:", "", *fence(f.linkedin), ""])
            count = f" ({len(f.resume)}/{f.limit} chars{'' if len(f.resume) <= f.limit else ', TOO LONG'})" \
                if f.limit else ""
            o.extend([f"Paste{count}:", "", *fence(f.resume), ""])
    return redact("\n".join(o) + "\n", terms)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    from build import parse

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", help="LinkedIn data export: the zip, or the directory it was unzipped to")
    ap.add_argument("--variant", default="general", help="résumé variant in src/ to compare against")
    ap.add_argument("--out", help="write the report here instead of stdout")
    a = ap.parse_args(argv)

    src = SRC / f"{a.variant}.md"
    if not src.exists():
        print(f"no such variant: {src}", file=sys.stderr)
        return 2
    try:
        li = read_export(Path(a.export))
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"cannot read export: {exc}", file=sys.stderr)
        return 2
    terms = load_denylist()
    res = from_resume(parse(src.read_text(encoding="utf-8"), src.name))
    findings = diff(res, li, terms)
    report = render_report(findings, terms, a.variant)
    drift = [f for f in findings if f.field != "not in export"]
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8", newline="\n")
        print(f"{len(drift)} difference(s); report written to {out}")
    else:
        sys.stdout.write(report)
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
