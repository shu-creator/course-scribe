"""Validate skill: Quality assurance for generated outputs.

This skill validates that generated summaries and questions:
1. Stay within syllabus scope
2. Are factually consistent with lecture content
3. Have correct calculation steps (for calculation questions)
4. Meet structural requirements

Input: Generated outputs (summary, questions) + source materials
Output: ValidationResult with issues and recommendations
"""

import re
from course_scribe.schemas.syllabus import Syllabus
from course_scribe.schemas.lecture import LectureContent
from course_scribe.schemas.summary import StructuredSummary
from course_scribe.schemas.questions import QuestionSet, CalculationQuestion
from course_scribe.schemas.validation import (
    ValidationResult,
    ValidationIssue,
    IssueSeverity,
    IssueCategory,
)


def validate_outputs(
    outputs: dict,
    lecture: dict,
    syllabus: dict,
) -> dict:
    """Validate generated outputs against source materials.

    Args:
        outputs: Dict containing any of:
            - summary: StructuredSummary as dict
            - questions: QuestionSet as dict
        lecture: LectureContent as dict
        syllabus: Syllabus as dict

    Returns:
        ValidationResult as dict
    """
    lecture_obj = LectureContent.model_validate(lecture)
    syllabus_obj = Syllabus.model_validate(syllabus)

    issues: list[ValidationIssue] = []
    checked_items: list[str] = []

    # Validate summary if present
    if "summary" in outputs:
        summary_obj = StructuredSummary.model_validate(outputs["summary"])
        summary_issues = _validate_summary(summary_obj, lecture_obj, syllabus_obj)
        issues.extend(summary_issues)
        checked_items.append("Summary structure and content")
        checked_items.append("Summary syllabus alignment")

    # Validate questions if present
    if "questions" in outputs:
        questions_obj = QuestionSet.model_validate(outputs["questions"])
        question_issues = _validate_questions(questions_obj, lecture_obj, syllabus_obj)
        issues.extend(question_issues)
        checked_items.append("Question scope validation")
        checked_items.append("Calculation question completeness")
        checked_items.append("Answer key consistency")

    # Determine overall validity
    is_valid = not any(i.severity == IssueSeverity.ERROR for i in issues)

    # Generate summary
    error_count = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
    warning_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
    summary_text = f"Found {error_count} errors and {warning_count} warnings."

    result = ValidationResult(
        is_valid=is_valid,
        issues=issues,
        checked_items=checked_items,
        summary=summary_text,
    )

    return result.model_dump()


def _validate_summary(
    summary: StructuredSummary,
    lecture: LectureContent,
    syllabus: Syllabus,
) -> list[ValidationIssue]:
    """Validate a structured summary."""
    issues = []

    # Check week number matches
    if summary.week_number != lecture.week_number:
        issues.append(
            ValidationIssue(
                category=IssueCategory.CONSISTENCY_ERROR,
                severity=IssueSeverity.ERROR,
                message=f"Summary week ({summary.week_number}) doesn't match lecture week ({lecture.week_number})",
                location="summary.week_number",
                suggestion="Ensure summary is generated from correct lecture",
            )
        )

    # Check syllabus alignment
    syllabus_week = syllabus.get_week(summary.week_number)
    if syllabus_week:
        # Check if summary claims to cover topics not in syllabus
        for section in summary.sections:
            for topic in section.syllabus_topics:
                if topic not in syllabus_week.topics:
                    issues.append(
                        ValidationIssue(
                            category=IssueCategory.SCOPE_VIOLATION,
                            severity=IssueSeverity.WARNING,
                            message=f"Topic '{topic}' referenced but not in syllabus week {summary.week_number}",
                            location=f"section: {section.heading}",
                            suggestion="Verify topic is within scope or remove reference",
                        )
                    )

    # Check for content not in lecture (scope violation)
    scope_issues = _check_content_scope(summary, lecture, syllabus)
    issues.extend(scope_issues)

    # Check structure
    if not summary.sections:
        issues.append(
            ValidationIssue(
                category=IssueCategory.FORMAT_ERROR,
                severity=IssueSeverity.ERROR,
                message="Summary has no sections",
                location="summary.sections",
                suggestion="Add at least one section to the summary",
            )
        )

    return issues


def _validate_questions(
    questions: QuestionSet,
    lecture: LectureContent,
    syllabus: Syllabus,
) -> list[ValidationIssue]:
    """Validate a question set."""
    issues = []

    # Check week number
    if questions.week_number != lecture.week_number:
        issues.append(
            ValidationIssue(
                category=IssueCategory.CONSISTENCY_ERROR,
                severity=IssueSeverity.ERROR,
                message=f"Questions week ({questions.week_number}) doesn't match lecture week ({lecture.week_number})",
                location="questions.week_number",
                suggestion="Ensure questions are generated from correct lecture",
            )
        )

    syllabus_week = syllabus.get_week(questions.week_number)

    # Validate each question type
    for eq in questions.essay_questions:
        eq_issues = _validate_essay_question(eq, lecture, syllabus_week)
        issues.extend(eq_issues)

    for cq in questions.calculation_questions:
        cq_issues = _validate_calculation_question(cq, lecture, syllabus_week)
        issues.extend(cq_issues)

    for mc in questions.multiple_choice_questions:
        mc_issues = _validate_mc_question(mc, lecture, syllabus_week)
        issues.extend(mc_issues)

    return issues


def _validate_essay_question(
    question,
    lecture: LectureContent,
    syllabus_week,
) -> list[ValidationIssue]:
    """Validate an essay question."""
    issues = []

    # Check if topic is in syllabus
    if syllabus_week:
        for topic in question.syllabus_topics:
            if topic not in syllabus_week.topics and topic not in syllabus_week.keywords:
                issues.append(
                    ValidationIssue(
                        category=IssueCategory.SCOPE_VIOLATION,
                        severity=IssueSeverity.WARNING,
                        message=f"Essay question topic '{topic}' not in syllabus",
                        location=f"question: {question.question_id}",
                        suggestion="Verify topic alignment with syllabus",
                    )
                )

    # Check if question has model answer
    if not question.model_answer:
        issues.append(
            ValidationIssue(
                category=IssueCategory.MISSING_CONTENT,
                severity=IssueSeverity.WARNING,
                message="Essay question missing model answer",
                location=f"question: {question.question_id}",
                suggestion="Add model answer with grading criteria",
            )
        )

    return issues


def _validate_calculation_question(
    question: CalculationQuestion,
    lecture: LectureContent,
    syllabus_week,
) -> list[ValidationIssue]:
    """Validate a calculation question.

    CRITICAL: Calculation questions must have:
    - Premises (given conditions)
    - Variable definitions with units
    - Step-by-step calculation
    - Final answer with units
    - Verification
    """
    issues = []

    # Check premises
    if not question.premises:
        issues.append(
            ValidationIssue(
                category=IssueCategory.MISSING_CONTENT,
                severity=IssueSeverity.ERROR,
                message="Calculation question missing premises",
                location=f"question: {question.question_id}",
                suggestion="Add clear premises/given conditions",
            )
        )

    # Check variables
    if not question.variables:
        issues.append(
            ValidationIssue(
                category=IssueCategory.MISSING_CONTENT,
                severity=IssueSeverity.ERROR,
                message="Calculation question missing variable definitions",
                location=f"question: {question.question_id}",
                suggestion="Define all variables with units",
            )
        )

    # Check calculation steps
    if not question.calculation_steps:
        issues.append(
            ValidationIssue(
                category=IssueCategory.MISSING_CONTENT,
                severity=IssueSeverity.ERROR,
                message="Calculation question missing calculation steps",
                location=f"question: {question.question_id}",
                suggestion="Add step-by-step calculation process",
            )
        )
    else:
        # Validate each step
        for step in question.calculation_steps:
            if not step.result:
                issues.append(
                    ValidationIssue(
                        category=IssueCategory.CALCULATION_ERROR,
                        severity=IssueSeverity.ERROR,
                        message=f"Step {step.step_number} missing result",
                        location=f"question: {question.question_id}, step {step.step_number}",
                        suggestion="Add result with units for each step",
                    )
                )

    # Check final answer
    if not question.final_answer:
        issues.append(
            ValidationIssue(
                category=IssueCategory.MISSING_CONTENT,
                severity=IssueSeverity.ERROR,
                message="Calculation question missing final answer",
                location=f"question: {question.question_id}",
                suggestion="Add final answer with units",
            )
        )

    # Check verification
    if not question.verification:
        issues.append(
            ValidationIssue(
                category=IssueCategory.MISSING_CONTENT,
                severity=IssueSeverity.WARNING,
                message="Calculation question missing verification",
                location=f"question: {question.question_id}",
                suggestion="Add verification/sanity check of the answer",
            )
        )

    # Check for units in final answer
    if question.final_answer and not _has_unit(question.final_answer):
        issues.append(
            ValidationIssue(
                category=IssueCategory.CALCULATION_ERROR,
                severity=IssueSeverity.WARNING,
                message="Final answer may be missing units",
                location=f"question: {question.question_id}",
                suggestion="Ensure final answer includes appropriate units",
            )
        )

    return issues


def _validate_mc_question(
    question,
    lecture: LectureContent,
    syllabus_week,
) -> list[ValidationIssue]:
    """Validate a multiple choice question."""
    issues = []

    # Check number of choices
    if len(question.choices) < 4:
        issues.append(
            ValidationIssue(
                category=IssueCategory.FORMAT_ERROR,
                severity=IssueSeverity.WARNING,
                message="Multiple choice question has fewer than 4 choices",
                location=f"question: {question.question_id}",
                suggestion="Add more choices for better assessment",
            )
        )

    # Check exactly one correct answer
    correct_count = sum(1 for c in question.choices if c.is_correct)
    if correct_count != 1:
        issues.append(
            ValidationIssue(
                category=IssueCategory.CONSISTENCY_ERROR,
                severity=IssueSeverity.ERROR,
                message=f"Multiple choice question has {correct_count} correct answers (should be 1)",
                location=f"question: {question.question_id}",
                suggestion="Ensure exactly one choice is marked correct",
            )
        )

    # Check correct_answer matches is_correct
    correct_labels = [c.label for c in question.choices if c.is_correct]
    if correct_labels and question.correct_answer not in correct_labels:
        issues.append(
            ValidationIssue(
                category=IssueCategory.CONSISTENCY_ERROR,
                severity=IssueSeverity.ERROR,
                message="correct_answer field doesn't match is_correct flag",
                location=f"question: {question.question_id}",
                suggestion="Ensure correct_answer matches the choice with is_correct=True",
            )
        )

    return issues


def _check_content_scope(
    summary: StructuredSummary,
    lecture: LectureContent,
    syllabus: Syllabus,
) -> list[ValidationIssue]:
    """Check if summary content stays within lecture scope."""
    issues = []

    # Get all keywords from lecture
    lecture_text_lower = lecture.raw_text.lower()

    # Check each section's key points
    for section in summary.sections:
        for point in section.key_points:
            # Simple heuristic: key points should have some basis in lecture
            point_words = set(point.lower().split())
            # Remove common words
            common = {"the", "a", "an", "is", "are", "was", "were", "を", "の", "が", "に", "は"}
            point_words -= common

            # Check if at least some content words appear in lecture
            matches = sum(1 for w in point_words if w in lecture_text_lower)
            if len(point_words) > 3 and matches < len(point_words) * 0.3:
                issues.append(
                    ValidationIssue(
                        category=IssueCategory.SCOPE_VIOLATION,
                        severity=IssueSeverity.WARNING,
                        message=f"Key point may contain content not from lecture: '{point[:50]}...'",
                        location=f"section: {section.heading}",
                        suggestion="Verify this content appears in lecture materials",
                    )
                )

    return issues


def _has_unit(text: str) -> bool:
    """Check if text contains a unit."""
    # Common unit patterns
    unit_patterns = [
        r"\b(m|km|cm|mm|s|h|min|kg|g|mg|N|J|W|V|A|Hz|Pa|mol|K|°C|°F)\b",
        r"\b(meter|second|hour|minute|kilogram|gram|newton|joule|watt|volt|ampere)\b",
        r"[²³]",  # Superscripts for squared/cubed
        r"/s\b|/h\b|/m\b",  # per-unit
    ]

    for pattern in unit_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


def validate_calculation_steps(steps: list[dict]) -> dict:
    """Standalone validation for calculation steps.

    Useful for validating calculation problems in isolation.

    Returns:
        dict with is_valid, errors, and step_results
    """
    errors = []
    step_results = []

    for i, step in enumerate(steps):
        step_num = step.get("step_number", i + 1)
        step_valid = True

        if not step.get("description"):
            errors.append(f"Step {step_num}: Missing description")
            step_valid = False

        if not step.get("calculation"):
            errors.append(f"Step {step_num}: Missing calculation")
            step_valid = False

        if not step.get("result"):
            errors.append(f"Step {step_num}: Missing result")
            step_valid = False
        elif not _has_unit(step.get("result", "")):
            errors.append(f"Step {step_num}: Result may be missing units")

        step_results.append({
            "step_number": step_num,
            "valid": step_valid,
        })

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "step_results": step_results,
    }
