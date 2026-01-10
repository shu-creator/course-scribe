"""CLI wrapper for course-scribe.

This is a THIN layer that handles file I/O and user interaction.
All processing logic is delegated to skill modules.
"""

import json
import sys
from pathlib import Path

import click

from course_scribe.skills import (
    ingest_document,
    align_with_syllabus,
    summarize_lecture,
    generate_questions,
    validate_outputs,
)
from course_scribe.core.readers import read_file, FileReadError, get_supported_formats
from course_scribe.core.project import (
    init_project,
    find_project_root,
    load_config,
    load_syllabus,
    add_lecture_record,
    get_output_path,
    project_exists,
    ProjectNotFoundError,
    ProjectExistsError,
)


def _read_file(path: Path, use_ocr: bool = False) -> str:
    """Read file content using the readers module."""
    try:
        return read_file(path, use_ocr=use_ocr)
    except FileReadError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _write_json(data: dict, path: Path) -> None:
    """Write dict as JSON file."""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(content: str, path: Path) -> None:
    """Write markdown file."""
    path.write_text(content, encoding="utf-8")


@click.group()
@click.version_option()
def cli():
    """course-scribe: Generate exam materials from lecture content."""
    pass


# =============================================================================
# Project Management Commands (init, add, status)
# =============================================================================


@cli.command()
@click.argument("syllabus_path", type=click.Path(exists=True, path_type=Path))
@click.option("--ocr", is_flag=True, help="Use OCR for scanned PDFs")
def init(syllabus_path: Path, ocr: bool):
    """Initialize a new project with a syllabus.

    This creates a .course-scribe directory and saves the parsed syllabus.
    After initialization, use 'add' to process lecture materials.

    Example:
        course-scribe init syllabus.pdf
        course-scribe add lecture_01.pptx
    """
    # Check if project already exists
    if project_exists():
        click.echo("Error: Project already exists in this directory.", err=True)
        click.echo("Use 'course-scribe status' to see current state.", err=True)
        sys.exit(1)

    click.echo(f"Initializing project with syllabus: {syllabus_path}")

    # Read and parse syllabus
    content = _read_file(syllabus_path, use_ocr=ocr)
    syllabus = ingest_document(
        content=content,
        document_type=syllabus_path.suffix.lstrip("."),
        source_filename=syllabus_path.name,
        is_syllabus=True,
    )

    # Initialize project
    try:
        root = init_project(syllabus_path, syllabus)
        course_name = syllabus.get("course_name", "Unknown Course")
        total_weeks = syllabus.get("total_weeks", 0)

        click.echo("")
        click.echo(f"Project initialized successfully!")
        click.echo(f"  Course: {course_name}")
        click.echo(f"  Weeks in syllabus: {total_weeks}")
        click.echo("")
        click.echo("Next steps:")
        click.echo("  course-scribe add <lecture_file> -w <week_number>")
        click.echo("  course-scribe status")

    except ProjectExistsError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("lecture_path", type=click.Path(exists=True, path_type=Path))
@click.option("-w", "--week", type=int, required=True, help="Week number for this lecture")
@click.option("--ocr", is_flag=True, help="Use OCR for scanned PDFs")
def add(lecture_path: Path, week: int, ocr: bool):
    """Add and process a lecture file.

    Requires a project to be initialized first with 'init'.
    Generates summary and questions, saves to output directory.

    Example:
        course-scribe add lecture_01.pptx -w 1
        course-scribe add lecture_02.docx -w 2
    """
    # Find project
    try:
        root = find_project_root()
    except ProjectNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Load syllabus
    syllabus = load_syllabus(root)
    output_dir = get_output_path(root)
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Processing: {lecture_path} (Week {week})")

    # Read and parse lecture
    click.echo("  Reading lecture content...")
    content = _read_file(lecture_path, use_ocr=ocr)
    lecture = ingest_document(
        content=content,
        document_type=lecture_path.suffix.lstrip("."),
        source_filename=lecture_path.name,
        week_number=week,
        is_syllabus=False,
    )

    prefix = f"week_{week:02d}"

    # Check alignment
    click.echo("  Checking syllabus alignment...")
    alignment = align_with_syllabus(lecture, syllabus)
    score = alignment.get("alignment_score", 0)
    click.echo(f"    Alignment score: {score:.1%}")

    # Generate summary
    click.echo("  Generating summary...")
    summary = summarize_lecture(lecture, syllabus, alignment)
    from course_scribe.schemas.summary import StructuredSummary
    summary_obj = StructuredSummary.model_validate(summary)
    _write_markdown(summary_obj.to_markdown(), output_dir / f"summary_{prefix}.md")

    # Generate questions
    click.echo("  Generating questions...")
    questions = generate_questions(lecture, syllabus)
    _write_json(questions, output_dir / f"questions_{prefix}.json")

    # Validate
    click.echo("  Validating outputs...")
    validation = validate_outputs(
        {"summary": summary, "questions": questions},
        lecture,
        syllabus,
    )
    from course_scribe.schemas.validation import ValidationResult
    val_obj = ValidationResult.model_validate(validation)
    _write_markdown(val_obj.to_report(), output_dir / f"validation_{prefix}.md")

    # Update project record
    add_lecture_record(
        week_number=week,
        source_file=str(lecture_path),
        has_summary=True,
        has_questions=True,
        root=root,
    )

    click.echo("")
    click.echo(f"Done! Files saved to: {output_dir}")
    click.echo(f"  - summary_{prefix}.md")
    click.echo(f"  - questions_{prefix}.json")
    click.echo(f"  - validation_{prefix}.md")

    if not val_obj.is_valid:
        click.echo("")
        click.echo("Warning: Validation found issues. Check validation report.", err=True)


@cli.command()
def status():
    """Show project status and processed lectures.

    Example:
        course-scribe status
    """
    try:
        root = find_project_root()
        config = load_config(root)
        syllabus = load_syllabus(root)
    except ProjectNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Course: {config.course_name}")
    click.echo(f"Syllabus: {config.syllabus_source}")
    click.echo(f"Output directory: {config.output_dir}")
    click.echo("")

    # Show syllabus weeks
    total_weeks = syllabus.get("total_weeks", 0)
    processed_weeks = {lec.week_number for lec in config.lectures}

    click.echo(f"Progress: {len(processed_weeks)}/{total_weeks} weeks processed")
    click.echo("")

    if config.lectures:
        click.echo("Processed lectures:")
        for lec in config.lectures:
            status_icons = []
            if lec.has_summary:
                status_icons.append("summary")
            if lec.has_questions:
                status_icons.append("questions")
            status_str = ", ".join(status_icons) if status_icons else "no outputs"
            click.echo(f"  Week {lec.week_number}: {lec.source_file} ({status_str})")
    else:
        click.echo("No lectures processed yet.")
        click.echo("Use 'course-scribe add <lecture_file> -w <week>' to add lectures.")

    # Show unprocessed weeks
    if total_weeks > 0:
        unprocessed = set(range(1, total_weeks + 1)) - processed_weeks
        if unprocessed:
            click.echo("")
            click.echo(f"Remaining weeks: {sorted(unprocessed)}")


# =============================================================================
# Low-level Commands (for advanced usage)
# =============================================================================


@cli.command()
@click.argument("syllabus_path", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output JSON file")
@click.option("--ocr", is_flag=True, help="Use OCR for scanned PDFs")
def ingest_syllabus(syllabus_path: Path, output: Path | None, ocr: bool):
    """Parse a syllabus file into structured format.

    Supported formats: .txt, .md, .pdf, .docx, .pptx
    """
    content = _read_file(syllabus_path, use_ocr=ocr)
    result = ingest_document(
        content=content,
        document_type=syllabus_path.suffix.lstrip("."),
        source_filename=syllabus_path.name,
        is_syllabus=True,
    )

    if output:
        _write_json(result, output)
        click.echo(f"Syllabus saved to: {output}")
    else:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))


@cli.command()
@click.argument("lecture_path", type=click.Path(exists=True, path_type=Path))
@click.option("-w", "--week", type=int, help="Week number (auto-detected from filename if not specified)")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output JSON file")
@click.option("--ocr", is_flag=True, help="Use OCR for scanned PDFs")
def ingest_lecture(lecture_path: Path, week: int | None, output: Path | None, ocr: bool):
    """Parse a lecture transcript/slides into structured format.

    Supported formats: .txt, .md, .pdf, .docx, .pptx
    """
    content = _read_file(lecture_path, use_ocr=ocr)
    result = ingest_document(
        content=content,
        document_type=lecture_path.suffix.lstrip("."),
        source_filename=lecture_path.name,
        week_number=week,
        is_syllabus=False,
    )

    if output:
        _write_json(result, output)
        click.echo(f"Lecture saved to: {output}")
    else:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))


@cli.command()
@click.argument("lecture_json", type=click.Path(exists=True, path_type=Path))
@click.argument("syllabus_json", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output JSON file")
@click.option("--strict/--no-strict", default=True, help="Enable strict scope checking")
def align(lecture_json: Path, syllabus_json: Path, output: Path | None, strict: bool):
    """Check alignment between lecture content and syllabus."""
    lecture = json.loads(lecture_json.read_text(encoding="utf-8"))
    syllabus = json.loads(syllabus_json.read_text(encoding="utf-8"))

    result = align_with_syllabus(lecture, syllabus, strict_mode=strict)

    if output:
        _write_json(result, output)
        click.echo(f"Alignment result saved to: {output}")
    else:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))

    # Print summary
    score = result.get("alignment_score", 0)
    click.echo(f"\nAlignment score: {score:.1%}")
    if result.get("uncovered_topics"):
        click.echo(f"Uncovered topics: {', '.join(result['uncovered_topics'])}")
    if result.get("potential_violations"):
        click.echo(f"Potential issues: {len(result['potential_violations'])}")


@cli.command()
@click.argument("lecture_json", type=click.Path(exists=True, path_type=Path))
@click.argument("syllabus_json", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output markdown file")
@click.option("--json-output", type=click.Path(path_type=Path), help="Also output as JSON")
def summarize(lecture_json: Path, syllabus_json: Path, output: Path | None, json_output: Path | None):
    """Generate structured summary from lecture content."""
    lecture = json.loads(lecture_json.read_text(encoding="utf-8"))
    syllabus = json.loads(syllabus_json.read_text(encoding="utf-8"))

    result = summarize_lecture(lecture, syllabus)

    # Export as markdown
    from course_scribe.schemas.summary import StructuredSummary

    summary_obj = StructuredSummary.model_validate(result)
    markdown = summary_obj.to_markdown()

    if output:
        _write_markdown(markdown, output)
        click.echo(f"Summary saved to: {output}")
    else:
        click.echo(markdown)

    if json_output:
        _write_json(result, json_output)
        click.echo(f"JSON saved to: {json_output}")


@cli.command()
@click.argument("lecture_json", type=click.Path(exists=True, path_type=Path))
@click.argument("syllabus_json", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output JSON file")
@click.option("--essay", type=int, default=2, help="Number of essay questions")
@click.option("--calc", type=int, default=1, help="Number of calculation questions")
@click.option("--mc", type=int, default=3, help="Number of multiple choice questions")
@click.option("--difficulty", type=click.Choice(["easy", "medium", "hard"]), default="medium")
def questions(
    lecture_json: Path,
    syllabus_json: Path,
    output: Path | None,
    essay: int,
    calc: int,
    mc: int,
    difficulty: str,
):
    """Generate exam questions from lecture content."""
    lecture = json.loads(lecture_json.read_text(encoding="utf-8"))
    syllabus = json.loads(syllabus_json.read_text(encoding="utf-8"))

    config = {
        "essay_count": essay,
        "calculation_count": calc,
        "mc_count": mc,
        "difficulty": difficulty,
    }

    result = generate_questions(lecture, syllabus, config)

    if output:
        _write_json(result, output)
        click.echo(f"Questions saved to: {output}")
    else:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))

    # Print summary
    from course_scribe.schemas.questions import QuestionSet

    qs = QuestionSet.model_validate(result)
    click.echo(f"\nGenerated: {len(qs.essay_questions)} essay, {len(qs.calculation_questions)} calculation, {len(qs.multiple_choice_questions)} MC questions")


@cli.command()
@click.argument("lecture_json", type=click.Path(exists=True, path_type=Path))
@click.argument("syllabus_json", type=click.Path(exists=True, path_type=Path))
@click.option("--summary", type=click.Path(exists=True, path_type=Path), help="Summary JSON to validate")
@click.option("--questions", "questions_file", type=click.Path(exists=True, path_type=Path), help="Questions JSON to validate")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output report file")
def validate(
    lecture_json: Path,
    syllabus_json: Path,
    summary: Path | None,
    questions_file: Path | None,
    output: Path | None,
):
    """Validate generated outputs against source materials."""
    lecture = json.loads(lecture_json.read_text(encoding="utf-8"))
    syllabus = json.loads(syllabus_json.read_text(encoding="utf-8"))

    outputs = {}
    if summary:
        outputs["summary"] = json.loads(summary.read_text(encoding="utf-8"))
    if questions_file:
        outputs["questions"] = json.loads(questions_file.read_text(encoding="utf-8"))

    if not outputs:
        click.echo("Error: Provide --summary and/or --questions to validate", err=True)
        sys.exit(1)

    result = validate_outputs(outputs, lecture, syllabus)

    # Generate report
    from course_scribe.schemas.validation import ValidationResult

    validation = ValidationResult.model_validate(result)
    report = validation.to_report()

    if output:
        _write_markdown(report, output)
        click.echo(f"Validation report saved to: {output}")
    else:
        click.echo(report)

    # Exit with error if validation failed
    if not validation.is_valid:
        sys.exit(1)


@cli.command()
@click.argument("syllabus_path", type=click.Path(exists=True, path_type=Path))
@click.argument("lecture_path", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output-dir", type=click.Path(path_type=Path), default=".", help="Output directory")
@click.option("-w", "--week", type=int, help="Week number")
@click.option("--ocr", is_flag=True, help="Use OCR for scanned PDFs")
def process(syllabus_path: Path, lecture_path: Path, output_dir: Path, week: int | None, ocr: bool):
    """Run full pipeline: ingest -> align -> summarize -> questions -> validate.

    Supported formats: .txt, .md, .pdf, .docx, .pptx
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo("Step 1: Ingesting syllabus...")
    syllabus_content = _read_file(syllabus_path, use_ocr=ocr)
    syllabus = ingest_document(
        content=syllabus_content,
        document_type=syllabus_path.suffix.lstrip("."),
        source_filename=syllabus_path.name,
        is_syllabus=True,
    )

    click.echo("Step 2: Ingesting lecture...")
    lecture_content = _read_file(lecture_path, use_ocr=ocr)
    lecture = ingest_document(
        content=lecture_content,
        document_type=lecture_path.suffix.lstrip("."),
        source_filename=lecture_path.name,
        week_number=week,
        is_syllabus=False,
    )

    week_num = lecture.get("week_number", 1)
    prefix = f"week_{week_num:02d}"

    click.echo("Step 3: Checking alignment...")
    alignment = align_with_syllabus(lecture, syllabus)
    click.echo(f"  Alignment score: {alignment['alignment_score']:.1%}")

    click.echo("Step 4: Generating summary...")
    summary = summarize_lecture(lecture, syllabus, alignment)
    from course_scribe.schemas.summary import StructuredSummary

    summary_obj = StructuredSummary.model_validate(summary)
    _write_markdown(summary_obj.to_markdown(), output_dir / f"summary_{prefix}.md")

    click.echo("Step 5: Generating questions...")
    questions = generate_questions(lecture, syllabus)
    _write_json(questions, output_dir / f"questions_{prefix}.json")

    click.echo("Step 6: Validating outputs...")
    validation = validate_outputs(
        {"summary": summary, "questions": questions},
        lecture,
        syllabus,
    )
    from course_scribe.schemas.validation import ValidationResult

    val_obj = ValidationResult.model_validate(validation)
    _write_markdown(val_obj.to_report(), output_dir / f"validation_{prefix}.md")

    click.echo(f"\nDone! Outputs saved to: {output_dir}")
    click.echo(f"  - summary_{prefix}.md")
    click.echo(f"  - questions_{prefix}.json")
    click.echo(f"  - validation_{prefix}.md")

    if not val_obj.is_valid:
        click.echo("\nWarning: Validation found issues. Check validation report.", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
