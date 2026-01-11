"""Pydantic schemas defining input/output contracts for each skill."""

from course_scribe.schemas.syllabus import Syllabus, SyllabusWeek
from course_scribe.schemas.lecture import LectureContent, LectureSection
from course_scribe.schemas.summary import StructuredSummary, SummarySection
from course_scribe.schemas.questions import (
    QuestionSet,
    Question,
    EssayQuestion,
    CalculationQuestion,
    MultipleChoiceQuestion,
    ModelAnswer,
    GradingCriteria,
)
from course_scribe.schemas.validation import ValidationResult, ValidationIssue

__all__ = [
    "Syllabus",
    "SyllabusWeek",
    "LectureContent",
    "LectureSection",
    "StructuredSummary",
    "SummarySection",
    "QuestionSet",
    "Question",
    "EssayQuestion",
    "CalculationQuestion",
    "MultipleChoiceQuestion",
    "ModelAnswer",
    "GradingCriteria",
    "ValidationResult",
    "ValidationIssue",
]
