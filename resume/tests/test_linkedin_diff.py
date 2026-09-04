"""Tests for linkedin_diff.py: LinkedIn data export vs. résumé source drift report.

The export fixture is a hand-written subset of the CSVs LinkedIn ships in
"Get a copy of your data". No real employer names appear here: the denylist
behaviour is exercised with the placeholder term "Acme Widgets".
"""

import zipfile

import pytest

import linkedin_diff as ld

ACME = "Acme Widgets"

PROFILE_CSV = (
    "First Name,Last Name,Maiden Name,Address,Birth Date,Headline,Summary,Industry,Zip Code,"
    "Geo Location,Twitter Handles,Websites,Instant Messengers\n"
    'Steven,Shine,,,,"Systems Engineer II | AD · PowerShell","Systems engineer with 15 years in IT.\n\n'
    'Runs infrastructure through change control.",Software,80202,"Denver, Colorado",,stevenshine.info,\n'
)

POSITIONS_CSV = (
    "Company Name,Title,Description,Location,Started On,Finished On\n"
    f'{ACME},Systems Engineer II,"Own two Active Directory forests.\n'
    '• Led the rebuild of nine domain controllers.","Denver, Colorado",Sep 2023,\n'
    'Poppulo,Infrastructure Engineer,"• Ran network, server, and storage operations.","Denver, Colorado",'
    "Apr 2021,Apr 2023\n"
)

EDUCATION_CSV = (
    "School Name,Start Date,End Date,Notes,Degree Name,Activities\n"
    "Louisiana State University,,May 2009,,\"BA, General Studies\",\n"
)

SKILLS_CSV = "Name\nActive Directory\nPowerShell\nTerraform\n"

CERTIFICATIONS_CSV = (
    "Name,Url,Authority,Started On,Finished On,License Number\n"
    "AWS Certified Cloud Practitioner,https://example.test/cert,Amazon Web Services,Jan 2026,,ABC123\n"
)

PROJECTS_CSV = (
    "Title,Description,Url,Started On,Finished On\n"
    'Cloud Resume Challenge,"Static site on AWS.",https://stevenshine.info,2023,2026\n'
)

FILES = {
    "Profile.csv": PROFILE_CSV,
    "Positions.csv": POSITIONS_CSV,
    "Education.csv": EDUCATION_CSV,
    "Skills.csv": SKILLS_CSV,
    "Certifications.csv": CERTIFICATIONS_CSV,
    "Projects.csv": PROJECTS_CSV,
}

RESUME_MD = f"""---
name: Steven Shine
title: Systems Engineer
headline: Systems Engineer II | AD · PowerShell
location: Denver, CO
variant: test
---

## Summary

Systems engineer with 15 years in IT.

Runs infrastructure through change control.

## Experience

### Systems Engineer II | Denver metro based software company
Sep 2023 – Present · Denver, CO
- Own two Active Directory forests.
- Led the rebuild of nine domain controllers.

### Infrastructure Engineer | Poppulo
Apr 2021 – Apr 2023 · Denver, CO
- Ran network, server, and storage operations.

## Projects

### Cloud Resume Challenge | stevenshine.info
2023 – 2026
- Static site on AWS.

## Skills

- **Directory & identity:** Active Directory, Group Policy
- **Automation & code:** PowerShell, Terraform

## Education

### BA, General Studies | Louisiana State University
May 2009
"""


@pytest.fixture
def export_dir(tmp_path):
    d = tmp_path / "export"
    d.mkdir()
    for name, body in FILES.items():
        (d / name).write_text(body, encoding="utf-8", newline="")
    return d


@pytest.fixture
def export_zip(tmp_path, export_dir):
    z = tmp_path / "Complete_LinkedInDataExport.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in export_dir.iterdir():
            zf.write(f, f.name)
    return z


@pytest.fixture
def resume():
    from build import parse
    return parse(RESUME_MD, "test.md")


# --------------------------------------------------------------------------- #
# Reading the export
# --------------------------------------------------------------------------- #

def test_read_export_dir_parses_positions_with_normalised_dates(export_dir):
    snap = ld.read_export(export_dir)
    assert [p.title for p in snap.positions] == ["Systems Engineer II", "Infrastructure Engineer"]
    first = snap.positions[0]
    assert first.company == ACME
    assert first.started == "Sep 2023"
    assert first.finished == ""          # current role: LinkedIn leaves Finished On empty
    assert first.location == "Denver, Colorado"
    assert first.description == "Own two Active Directory forests.\n• Led the rebuild of nine domain controllers."


def test_read_export_zip_gives_same_result_as_dir(export_dir, export_zip):
    assert ld.read_export(export_zip) == ld.read_export(export_dir)


def test_read_export_reads_profile_skills_education_certs_projects(export_dir):
    snap = ld.read_export(export_dir)
    assert snap.headline == "Systems Engineer II | AD · PowerShell"
    assert snap.about == "Systems engineer with 15 years in IT.\n\nRuns infrastructure through change control."
    assert snap.skills == ["Active Directory", "PowerShell", "Terraform"]
    assert snap.education[0].school == "Louisiana State University"
    assert snap.education[0].degree == "BA, General Studies"
    assert snap.education[0].finished == "May 2009"
    assert snap.certifications[0].name == "AWS Certified Cloud Practitioner"
    assert snap.certifications[0].authority == "Amazon Web Services"
    assert snap.projects[0].title == "Cloud Resume Challenge"
    assert snap.projects[0].started == "2023"
    assert snap.projects[0].finished == "2026"


def test_read_export_tolerates_bom_and_notes_preamble(tmp_path):
    d = tmp_path / "export"
    d.mkdir()
    (d / "Skills.csv").write_text(
        "﻿Notes:\n\"Some files may take longer to appear.\"\n\nName\nPowerShell\n",
        encoding="utf-8", newline="")
    snap = ld.read_export(d)
    assert snap.skills == ["PowerShell"]


def test_read_export_missing_files_are_empty_not_errors(tmp_path):
    d = tmp_path / "export"
    d.mkdir()
    snap = ld.read_export(d)
    assert snap.positions == [] and snap.skills == [] and snap.headline == ""


# --------------------------------------------------------------------------- #
# Converting the résumé
# --------------------------------------------------------------------------- #

def test_from_resume_splits_date_ranges_and_marks_present_as_open(resume):
    snap = ld.from_resume(resume)
    cur, prev = snap.positions
    assert (cur.started, cur.finished) == ("Sep 2023", "")
    assert (prev.started, prev.finished) == ("Apr 2021", "Apr 2023")
    assert cur.company == "Denver metro based software company"
    assert cur.location == "Denver, CO"


def test_from_resume_description_matches_linkedin_paste_block(resume):
    snap = ld.from_resume(resume)
    assert snap.positions[0].description == (
        "• Own two Active Directory forests.\n• Led the rebuild of nine domain controllers.")


def test_from_resume_headline_about_skills_education_projects(resume):
    snap = ld.from_resume(resume)
    assert snap.headline == "Systems Engineer II | AD · PowerShell"
    assert snap.about == "Systems engineer with 15 years in IT.\n\nRuns infrastructure through change control."
    assert snap.skills == ["Active Directory", "Group Policy", "PowerShell", "Terraform"]
    assert snap.education == [ld.Education("Louisiana State University", "BA, General Studies", "", "May 2009")]
    assert snap.projects[0].title == "Cloud Resume Challenge"
    assert (snap.projects[0].started, snap.projects[0].finished) == ("2023", "2026")
    assert snap.projects[0].description == "• Static site on AWS."


# --------------------------------------------------------------------------- #
# Comparing the two sides
# --------------------------------------------------------------------------- #

TERMS = [ACME]


def findings(resume, export_dir, terms=TERMS):
    return ld.diff(ld.from_resume(resume), ld.read_export(export_dir), terms)


def by(fs, section, field=None):
    return [f for f in fs if f.section == section and (field is None or f.field == field)]


def test_diff_of_snapshot_against_itself_is_clean(resume):
    snap = ld.from_resume(resume)
    assert ld.diff(snap, snap, TERMS) == []


def test_diff_reports_description_drift_with_paste_block(resume, export_dir):
    fs = by(findings(resume, export_dir), "Experience", "description")
    assert len(fs) == 1
    f = fs[0]
    assert f.item.startswith("Systems Engineer II")
    assert f.resume == "• Own two Active Directory forests.\n• Led the rebuild of nine domain controllers."
    assert f.linkedin == "Own two Active Directory forests.\n• Led the rebuild of nine domain controllers."
    assert f.limit == 2000


def test_diff_ignores_company_when_linkedin_company_is_denylisted(resume, export_dir):
    fs = findings(resume, export_dir)
    assert by(fs, "Experience", "company") == []


def test_diff_reports_company_when_it_genuinely_differs(resume, export_dir):
    fs = findings(resume, export_dir, terms=[])          # nothing is anonymised now
    companies = by(fs, "Experience", "company")
    assert len(companies) == 1
    assert companies[0].linkedin == ACME
    assert companies[0].resume == "Denver metro based software company"


def test_diff_treats_full_state_name_and_united_states_suffix_as_same_location(resume, export_dir):
    assert by(findings(resume, export_dir), "Experience", "location") == []


def test_diff_reports_position_missing_on_linkedin(resume, export_dir):
    (export_dir / "Positions.csv").write_text(POSITIONS_CSV.splitlines(keepends=True)[0] +
                                              POSITIONS_CSV.splitlines(keepends=True)[1] +
                                              POSITIONS_CSV.splitlines(keepends=True)[2],
                                              encoding="utf-8", newline="")
    fs = by(findings(resume, export_dir), "Experience", "missing on LinkedIn")
    assert [f.item for f in fs] == ["Infrastructure Engineer · Poppulo · Apr 2021 – Apr 2023 · Denver, CO"]
    assert fs[0].resume == "• Ran network, server, and storage operations."


def test_diff_reports_linkedin_position_not_in_resume(resume, export_dir):
    with (export_dir / "Positions.csv").open("a", encoding="utf-8", newline="") as fh:
        fh.write('Old Co,Intern,"Fetched coffee.","Denver, Colorado",Jan 2010,Jun 2010\n')
    fs = by(findings(resume, export_dir), "Experience", "not in résumé")
    assert [f.item for f in fs] == ["Intern · Old Co · Jan 2010 – Jun 2010 · Denver, Colorado"]


def test_diff_reports_skills_missing_on_linkedin_and_extra_on_linkedin(resume, export_dir):
    fs = findings(resume, export_dir)
    assert [f.resume for f in by(fs, "Skills", "missing on LinkedIn")] == ["Group Policy"]
    assert by(fs, "Skills", "not in résumé") == []
    (export_dir / "Skills.csv").write_text(SKILLS_CSV + "Juggling\n", encoding="utf-8", newline="")
    fs = findings(resume, export_dir)
    assert [f.linkedin for f in by(fs, "Skills", "not in résumé")] == ["Juggling"]


def test_diff_matches_education_by_school_and_compares_degree(resume, export_dir):
    assert by(findings(resume, export_dir), "Education") == []
    (export_dir / "Education.csv").write_text(
        EDUCATION_CSV.replace("BA, General Studies", "BS, General Studies"), encoding="utf-8", newline="")
    fs = by(findings(resume, export_dir), "Education", "degree")
    assert len(fs) == 1 and fs[0].resume == "BA, General Studies"


def test_diff_reports_certification_missing_on_linkedin_and_extra_on_linkedin(resume, export_dir):
    fs = findings(resume, export_dir)
    assert [f.linkedin for f in by(fs, "Certifications", "not in résumé")] == ["AWS Certified Cloud Practitioner"]
    md = RESUME_MD + "\n## Certifications\n\n### CompTIA Security+ | CompTIA\n2026\n"
    from build import parse
    fs = ld.diff(ld.from_resume(parse(md, "t.md")), ld.read_export(export_dir), TERMS)
    assert [f.resume for f in by(fs, "Certifications", "missing on LinkedIn")] == ["CompTIA Security+"]


def test_diff_compares_project_description(resume, export_dir):
    fs = by(findings(resume, export_dir), "Projects", "description")
    assert len(fs) == 1 and fs[0].resume == "• Static site on AWS."


def test_diff_normalises_bullet_glyphs_and_whitespace_before_comparing(resume, export_dir):
    (export_dir / "Projects.csv").write_text(
        PROJECTS_CSV.replace('"Static site on AWS."', '"-  Static site on AWS.  "'), encoding="utf-8", newline="")
    assert by(findings(resume, export_dir), "Projects", "description") == []


def test_diff_flags_denylist_terms_in_linkedin_text_fields_but_not_company(resume, export_dir):
    assert by(findings(resume, export_dir), "Privacy") == []
    (export_dir / "Profile.csv").write_text(
        PROFILE_CSV.replace("Runs infrastructure", f"Runs {ACME} infrastructure"), encoding="utf-8", newline="")
    fs = by(findings(resume, export_dir), "Privacy")
    assert [(f.item, f.linkedin) for f in fs] == [("About", ACME)]


POSITIONS_HEADER = "Company Name,Title,Description,Location,Started On,Finished On\n"


def test_diff_matches_positions_by_company_and_dates_when_titles_were_rewritten(resume, tmp_path):
    d = tmp_path / "export"
    d.mkdir()
    (d / "Positions.csv").write_text(
        POSITIONS_HEADER +
        "Denver metro based company,IT System Engineer II - IT Systems,,,Nov 2023,\n"
        'Poppulo,INFRAOPS ENGINEER I,"Provided first-level support.","Denver, Colorado, United States",'
        "Apr 2021,May 2023\n", encoding="utf-8", newline="")
    fs = findings(resume, d)
    assert by(fs, "Experience", "missing on LinkedIn") == []
    assert by(fs, "Experience", "not in résumé") == []
    assert [(f.linkedin, f.resume) for f in by(fs, "Experience", "title")] == [
        ("IT System Engineer II - IT Systems", "Systems Engineer II"),
        ("INFRAOPS ENGINEER I", "Infrastructure Engineer")]
    assert [(f.linkedin, f.resume) for f in by(fs, "Experience", "dates")] == [
        ("Nov 2023 – Present", "Sep 2023 – Present"),
        ("Apr 2021 – May 2023", "Apr 2021 – Apr 2023")]


def test_diff_pairs_sibling_roles_at_one_company_by_best_score(tmp_path):
    from build import parse
    md = RESUME_MD.replace("## Projects", """### System Administrator | Four Winds Interactive
Nov 2020 – Apr 2021 · Denver, CO
- Deployed systems.

### Associate System Administrator | Four Winds Interactive
Jan 2015 – Nov 2020 · Denver, CO
- Managed servers.

### Senior Hardware Specialist and Integration Technician | Four Winds Interactive
2011 – 2015 · Denver, CO
- Delivered signage.

## Projects""")
    d = tmp_path / "export"
    d.mkdir()
    (d / "Positions.csv").write_text(
        POSITIONS_HEADER +
        "Four Winds Interactive,IT Systems Administrator,\"Deployed systems.\",,Nov 2019,Apr 2021\n"
        "Four Winds Interactive,Associate System Administrator,\"Managed servers.\",,Jan 2015,Nov 2019\n"
        "Four Winds Interactive,Senior Hardware Specialist,\"Delivered signage.\",,Jul 2014,Jan 2015\n"
        "Four Winds Interactive,Hardware Specialist,,,2013,Jul 2014\n"
        "Four Winds Interactive,Field Services Technician,,\"Denver, CO\",2011,2013\n",
        encoding="utf-8", newline="")
    fs = ld.diff(ld.from_resume(parse(md, "t.md")), ld.read_export(d), TERMS)
    exp = [f for f in fs if f.section == "Experience" and "Four Winds" in f.item]
    assert [f.item.split(" · ")[0] for f in exp if f.field == "not in résumé"] == [
        "Hardware Specialist", "Field Services Technician"]
    assert [f for f in exp if f.field == "missing on LinkedIn"] == []
    assert [(f.resume, f.linkedin) for f in exp if f.field == "title"] == [
        ("System Administrator", "IT Systems Administrator"),
        ("Senior Hardware Specialist and Integration Technician", "Senior Hardware Specialist")]


def test_diff_treats_year_only_resume_dates_as_equal_to_linkedin_month_dates(tmp_path):
    from build import parse
    md = RESUME_MD.replace("## Projects", """### Field Technician | Old Co
2011 – 2015 · Denver, CO
- Fixed things.

## Projects""")
    d = tmp_path / "export"
    d.mkdir()
    (d / "Positions.csv").write_text(
        POSITIONS_HEADER + 'Old Co,Field Technician,"• Fixed things.","Denver, CO",Jul 2011,Jan 2015\n',
        encoding="utf-8", newline="")
    fs = ld.diff(ld.from_resume(parse(md, "t.md")), ld.read_export(d), TERMS)
    assert [f for f in fs if f.section == "Experience" and "Field Technician" in f.item] == []


def test_diff_skips_sections_whose_file_is_absent_from_the_export(resume, tmp_path):
    d = tmp_path / "export"
    d.mkdir()
    (d / "Positions.csv").write_text(POSITIONS_HEADER, encoding="utf-8", newline="")
    fs = findings(resume, d)
    assert by(fs, "Skills", "missing on LinkedIn") == []
    assert by(fs, "Headline", "text") == [] and by(fs, "About", "text") == []
    assert by(fs, "Education", "missing on LinkedIn") == [] and by(fs, "Projects", "missing on LinkedIn") == []
    assert sorted(f.section for f in fs if f.field == "not in export") == [
        "About", "Certifications", "Education", "Headline", "Projects", "Skills"]
    assert len(by(fs, "Experience", "missing on LinkedIn")) == 2
    text = ld.render_report(fs, TERMS)
    assert "not in export" in text


def test_resume_skills_split_on_top_level_commas_and_drop_parentheticals():
    from build import linkedin_skills, parse
    md = RESUME_MD.replace(
        "- **Directory & identity:** Active Directory, Group Policy",
        "- **Cloud:** AWS (S3, CloudFront, Lambda), Windows Server 2012 R2–2025, PowerShell 5.1/7 (modules, Pester)")
    assert linkedin_skills(parse(md, "t.md")) == [
        "AWS", "Windows Server 2012 R2–2025", "PowerShell 5.1/7", "PowerShell", "Terraform"]


def test_diff_counts_linkedin_tag_as_covering_a_more_specific_resume_skill(resume, export_dir):
    from build import parse
    md = RESUME_MD.replace("- **Automation & code:** PowerShell, Terraform",
                           "- **Automation & code:** PowerShell, Terraform, Windows Server 2012 R2–2025, VMware vSphere/ESXi 8")
    (export_dir / "Skills.csv").write_text(SKILLS_CSV + "Windows Server\nVMware\n", encoding="utf-8", newline="")
    fs = ld.diff(ld.from_resume(parse(md, "t.md")), ld.read_export(export_dir), TERMS)
    assert [f.resume for f in by(fs, "Skills", "missing on LinkedIn")] == ["Group Policy"]
    assert by(fs, "Skills", "not in résumé") == []


def test_diff_counts_linkedin_canonical_name_as_covering_resume_short_form(resume, export_dir):
    from build import parse
    md = RESUME_MD.replace("- **Automation & code:** PowerShell, Terraform",
                           "- **Automation & code:** PowerShell, Terraform, T-SQL, Python, Cisco ISE, AWS, Teams")
    (export_dir / "Skills.csv").write_text(
        SKILLS_CSV + "Transact-SQL (T-SQL)\nPython (Programming Language)\n"
        "Cisco Identity Services Engine (ISE)\nAmazon Web Services (AWS)\nMicrosoft Teams\n",
        encoding="utf-8", newline="")
    fs = ld.diff(ld.from_resume(parse(md, "t.md")), ld.read_export(export_dir), TERMS)
    assert [f.resume for f in by(fs, "Skills", "missing on LinkedIn")] == ["Group Policy"]
    assert by(fs, "Skills", "not in résumé") == []


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #

def test_report_says_no_drift_when_clean(resume):
    snap = ld.from_resume(resume)
    assert "No drift" in ld.render_report([], TERMS)


def test_report_redacts_denylist_terms_everywhere(resume, export_dir):
    fs = findings(resume, export_dir, terms=[])
    text = ld.render_report(fs, TERMS)
    assert ACME not in text
    assert "[redacted]" in text


def test_report_shows_paste_block_with_char_count(resume, export_dir):
    text = ld.render_report(findings(resume, export_dir), TERMS)
    assert "```" in text
    assert "/2000" in text
    assert "• Own two Active Directory forests." in text


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def test_main_exit_codes_and_out_file(tmp_path, export_dir, monkeypatch, capsys):
    src = tmp_path / "src"
    src.mkdir()
    (src / "test.md").write_text(RESUME_MD, encoding="utf-8")
    monkeypatch.setattr(ld, "SRC", src)
    monkeypatch.setattr(ld, "load_denylist", lambda: TERMS)
    out = tmp_path / "drift.md"
    assert ld.main([str(export_dir), "--variant", "test", "--out", str(out)]) == 1
    assert "Experience" in out.read_text(encoding="utf-8")
    assert ACME not in out.read_text(encoding="utf-8")
    # a clean run: export generated from the résumé itself
    assert ld.main(["/nonexistent/path", "--variant", "test"]) == 2
