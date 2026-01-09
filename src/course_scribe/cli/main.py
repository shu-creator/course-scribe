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


def _read_file(path: Path) -> str:
    """Read file content, handling PDF if needed."""
    if path.suffix.lower() == ".pdf":
        try:
            import pdfplumber

            with pdfplumber.open(path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return text
        except ImportError:
            click.echo("Error: pdfplumber required for PDF files. Install with: pip install pdfplumber", err=True)
            sys.exit(1)
    else:
        return path.read_text(encoding="utf-8")


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


@cli.command()
@click.argument("syllabus_path", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output JSON file")
def ingest_syllabus(syllabus_path: Path, output: Path | None):
    """Parse a syllabus file into structured format."""
    content = _read_file(syllabus_path)
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
def ingest_lecture(lecture_path: Path, week: int | None, output: Path | None):
    """Parse a lecture transcript/slides into structured format."""
    content = _read_file(lecture_path)
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
def process(syllabus_path: Path, lecture_path: Path, output_dir: Path, week: int | None):
    """Run full pipeline: ingest -> align -> summarize -> questions -> validate."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo("Step 1: Ingesting syllabus...")
    syllabus_content = _read_file(syllabus_path)
    syllabus = ingest_document(
        content=syllabus_content,
        document_type=syllabus_path.suffix.lstrip("."),
        source_filename=syllabus_path.name,
        is_syllabus=True,
    )

    click.echo("Step 2: Ingesting lecture...")
    lecture_content = _read_file(lecture_path)
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
