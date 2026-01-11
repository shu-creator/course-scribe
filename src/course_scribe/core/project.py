"""Project management for course-scribe.

Handles project initialization, configuration, and state tracking.
Project data is stored in a .course-scribe directory.
"""

import json
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, Field


# Default project directory name
PROJECT_DIR = ".course-scribe"
CONFIG_FILE = "config.json"
SYLLABUS_FILE = "syllabus.json"
LECTURES_DIR = "lectures"
OUTPUT_DIR = "output"


class LectureRecord(BaseModel):
    """Record of a processed lecture."""

    week_number: int
    source_file: str
    processed_at: str
    has_summary: bool = False
    has_questions: bool = False


class ProjectConfig(BaseModel):
    """Project configuration."""

    course_name: str = ""
    syllabus_source: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    lectures: list[LectureRecord] = Field(default_factory=list)
    output_dir: str = OUTPUT_DIR


class ProjectNotFoundError(Exception):
    """Raised when no project is found in the current directory."""
    pass


class ProjectExistsError(Exception):
    """Raised when trying to init in a directory that already has a project."""
    pass


def find_project_root(start_path: Path | None = None) -> Path:
    """Find the project root by looking for .course-scribe directory.

    Args:
        start_path: Starting path to search from. Defaults to current directory.

    Returns:
        Path to project root (directory containing .course-scribe)

    Raises:
        ProjectNotFoundError: If no project is found
    """
    current = start_path or Path.cwd()

    # Search up to 10 levels up
    for _ in range(10):
        project_dir = current / PROJECT_DIR
        if project_dir.exists() and project_dir.is_dir():
            return current
        parent = current.parent
        if parent == current:  # Reached root
            break
        current = parent

    raise ProjectNotFoundError(
        "No course-scribe project found.\n"
        "Run 'course-scribe init <syllabus>' to create a new project."
    )


def get_project_dir(root: Path | None = None) -> Path:
    """Get the .course-scribe directory path."""
    if root is None:
        root = find_project_root()
    return root / PROJECT_DIR


def load_config(root: Path | None = None) -> ProjectConfig:
    """Load project configuration."""
    project_dir = get_project_dir(root)
    config_path = project_dir / CONFIG_FILE

    if not config_path.exists():
        raise ProjectNotFoundError("Project config not found.")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    return ProjectConfig.model_validate(data)


def save_config(config: ProjectConfig, root: Path | None = None) -> None:
    """Save project configuration."""
    project_dir = get_project_dir(root)
    config_path = project_dir / CONFIG_FILE
    config_path.write_text(
        json.dumps(config.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_syllabus(root: Path | None = None) -> dict:
    """Load the cached syllabus data."""
    project_dir = get_project_dir(root)
    syllabus_path = project_dir / SYLLABUS_FILE

    if not syllabus_path.exists():
        raise ProjectNotFoundError("Syllabus not found. Run 'course-scribe init' first.")

    return json.loads(syllabus_path.read_text(encoding="utf-8"))


def save_syllabus(syllabus: dict, root: Path | None = None) -> None:
    """Save syllabus data."""
    project_dir = get_project_dir(root)
    syllabus_path = project_dir / SYLLABUS_FILE
    syllabus_path.write_text(
        json.dumps(syllabus, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def init_project(
    syllabus_path: Path,
    syllabus_data: dict,
    root: Path | None = None,
) -> Path:
    """Initialize a new project.

    Args:
        syllabus_path: Path to the original syllabus file
        syllabus_data: Parsed syllabus data
        root: Project root directory. Defaults to current directory.

    Returns:
        Path to the project root

    Raises:
        ProjectExistsError: If project already exists
    """
    root = root or Path.cwd()
    project_dir = root / PROJECT_DIR

    if project_dir.exists():
        raise ProjectExistsError(
            f"Project already exists in {root}.\n"
            "Use 'course-scribe status' to see current state."
        )

    # Create directory structure
    project_dir.mkdir(parents=True)
    (project_dir / LECTURES_DIR).mkdir()
    (root / OUTPUT_DIR).mkdir(exist_ok=True)

    # Save syllabus
    save_syllabus(syllabus_data, root)

    # Create config
    config = ProjectConfig(
        course_name=syllabus_data.get("course_name", "Unknown Course"),
        syllabus_source=str(syllabus_path),
    )
    save_config(config, root)

    return root


def add_lecture_record(
    week_number: int,
    source_file: str,
    has_summary: bool = True,
    has_questions: bool = True,
    root: Path | None = None,
) -> None:
    """Add or update a lecture record."""
    config = load_config(root)

    # Check if lecture already exists
    for lecture in config.lectures:
        if lecture.week_number == week_number:
            # Update existing
            lecture.source_file = source_file
            lecture.processed_at = datetime.now().isoformat()
            lecture.has_summary = has_summary
            lecture.has_questions = has_questions
            save_config(config, root)
            return

    # Add new
    config.lectures.append(
        LectureRecord(
            week_number=week_number,
            source_file=source_file,
            processed_at=datetime.now().isoformat(),
            has_summary=has_summary,
            has_questions=has_questions,
        )
    )
    # Sort by week number
    config.lectures.sort(key=lambda x: x.week_number)
    save_config(config, root)


def get_output_path(root: Path | None = None) -> Path:
    """Get the output directory path."""
    if root is None:
        root = find_project_root()
    config = load_config(root)
    return root / config.output_dir


def project_exists(root: Path | None = None) -> bool:
    """Check if a project exists."""
    try:
        find_project_root(root)
        return True
    except ProjectNotFoundError:
        return False
