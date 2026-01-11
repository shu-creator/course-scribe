"""Reusable skill modules for course-scribe.

Each skill is a pure function: dict -> dict (or Pydantic model -> Pydantic model).
No file I/O within skills - that belongs in the CLI layer.
"""

from course_scribe.skills.ingest import ingest_document
from course_scribe.skills.align_syllabus import align_with_syllabus
from course_scribe.skills.summarize import summarize_lecture
from course_scribe.skills.generate_questions import generate_questions
from course_scribe.skills.validate import validate_outputs

__all__ = [
    "ingest_document",
    "align_with_syllabus",
    "summarize_lecture",
    "generate_questions",
    "validate_outputs",
]
