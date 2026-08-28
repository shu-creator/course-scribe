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

    has_summary = "summary" in outputs
    has_questions = "questions" in outputs
    summary_obj = None
    questions_obj = None

    if not has_summary and not has_questions:
        issues.append(
            ValidationIssue(
                category=IssueCategory.MISSING_CONTENT,
                severity=IssueSeverity.ERROR,
                message="Outputs are empty; no summary or questions were provided",
                location="outputs",
                suggestion="Provide summary and/or questions based only on lecture content",
            )
        )
        checked_items.append("Output presence")
    else:
        # Validate summary if present
        if has_summary:
            summary_obj = StructuredSummary.model_validate(outputs["summary"])
            summary_issues = _validate_summary(summary_obj, lecture_obj, syllabus_obj)
            issues.extend(summary_issues)
            checked_items.append("Summary structure and content")
            checked_items.append("Summary syllabus alignment")

        # Validate questions if present
        if has_questions:
            questions_obj = QuestionSet.model_validate(outputs["questions"])
            question_issues = _validate_questions(questions_obj, lecture_obj, syllabus_obj)
            issues.extend(question_issues)
            checked_items.append("Question scope validation")
            checked_items.append("Calculation question completeness")
            checked_items.append("Answer key consistency")

        issues.extend(
            _check_grounding_fail_closed(lecture_obj, summary_obj, questions_obj)
        )
        checked_items.append("Lecture grounding of output material")

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


# Fail-closed grounding applies only to long, clearly unsupported material.
# Short or 2+ token lexical overlap stays with the warning-level heuristic below.
# A single lecture-derived token does not mask an otherwise unsupported remainder.
_MIN_UNGROUNDED_CHARS = 40
_MIN_UNGROUNDED_TOKENS = 8
_MAX_FAIL_CLOSED_TOKEN_MATCHES = 1
_MIN_CJK_PARAPHRASE_CHARS = 20
_CJK_BIGRAM_OVERLAP = 0.5
_TOKEN_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9_-]*|[0-9]+(?:\.[0-9]+)?|[ぁ-んァ-ン一-龯]+"
)
_CJK_CHAR_RE = re.compile(r"[ぁ-んァ-ン一-龯ー]")
_LATIN_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "can", "and", "or",
    "but", "if", "then", "else", "when", "where", "what", "which",
    "who", "how", "this", "that", "these", "those", "it", "its",
}


def _normalize_text(text: str) -> str:
    """Collapse whitespace and lowercase for containment checks."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _content_tokens(text: str) -> set[str]:
    """Distinctive tokens used only for the fail-closed overlap gate."""
    tokens = {m.group(0).lower() for m in _TOKEN_RE.finditer(text)}
    tokens -= _LATIN_STOPWORDS
    return {t for t in tokens if len(t) >= 3}


def _cjk_chars(text: str) -> str:
    return "".join(_CJK_CHAR_RE.findall(text))


def _char_ngrams(text: str, n: int = 2) -> set[str]:
    if len(text) < n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def _is_cjk_paraphrase_grounded(text: str, lecture_body: str) -> bool:
    """True for lecture-grounded Japanese paraphrases that are not substrings."""
    text_cjk = _cjk_chars(text)
    lecture_cjk = _cjk_chars(lecture_body)
    if (
        len(text_cjk) < _MIN_CJK_PARAPHRASE_CHARS
        or len(lecture_cjk) < _MIN_CJK_PARAPHRASE_CHARS
    ):
        return False
    text_grams = _char_ngrams(text_cjk, 2)
    lecture_grams = _char_ngrams(lecture_cjk, 2)
    if not text_grams:
        return False
    overlap = len(text_grams & lecture_grams) / len(text_grams)
    return overlap >= _CJK_BIGRAM_OVERLAP


def _is_clearly_ungrounded(text: str, lecture_body: str) -> bool:
    """True only for clearly unsupported material, not ambiguous overlap.

    Direct containment in the lecture body is grounded. A 40+ character
    Japanese paraphrase with high character overlap is grounded even when it
    is not an exact substring. Short fragments and 2+ distinctive-token
    overlap are left to the warning-level heuristic. A single lecture-derived
    token does not mask a long unsupported remainder.
    """
    if not isinstance(text, str):
        return False
    stripped = text.strip()
    if not stripped:
        return False

    text_norm = _normalize_text(stripped)
    lecture_norm = _normalize_text(lecture_body)
    if text_norm and lecture_norm and text_norm in lecture_norm:
        return False

    if _is_cjk_paraphrase_grounded(stripped, lecture_body):
        return False

    tokens = _content_tokens(stripped)
    is_long_statement = (
        len(text_norm) >= _MIN_UNGROUNDED_CHARS
        or len(tokens) >= _MIN_UNGROUNDED_TOKENS
    )
    if not is_long_statement:
        return False

    if not tokens:
        return True

    lecture_lower = lecture_body.lower()
    matches = sum(1 for token in tokens if token in lecture_lower)
    return matches <= _MAX_FAIL_CLOSED_TOKEN_MATCHES


def _ungrounded_issue(location: str, text: str) -> ValidationIssue:
    preview = text.strip()
    if len(preview) > 80:
        preview = preview[:80] + "..."
    return ValidationIssue(
        category=IssueCategory.SCOPE_VIOLATION,
        severity=IssueSeverity.ERROR,
        message=f"Unsupported material not grounded in lecture content: '{preview}'",
        location=location,
        suggestion="Replace with content taken from the lecture body",
    )


def _collect_ungrounded(
    issues: list[ValidationIssue],
    lecture_body: str,
    location: str,
    text: str,
) -> None:
    if _is_clearly_ungrounded(text, lecture_body):
        issues.append(_ungrounded_issue(location, text))


def _variable_location(question_index: int, key: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        return f"questions.calculation_questions[{question_index}].variables.{key}"
    return f"questions.calculation_questions[{question_index}].variables[{key!r}]"


def _check_grounding_fail_closed(
    lecture: LectureContent,
    summary: StructuredSummary | None,
    questions: QuestionSet | None,
) -> list[ValidationIssue]:
    """Fail closed when material fields contain clearly lecture-external text."""
    issues: list[ValidationIssue] = []
    lecture_body = lecture.raw_text
    if lecture.sections:
        lecture_body = lecture_body + "\n" + lecture.get_full_text()

    if summary is not None:
        for i, section in enumerate(summary.sections):
            _collect_ungrounded(
                issues,
                lecture_body,
                f"summary.sections[{i}].content",
                section.content,
            )
            for j, point in enumerate(section.key_points):
                _collect_ungrounded(
                    issues,
                    lecture_body,
                    f"summary.sections[{i}].key_points[{j}]",
                    point,
                )
        for j, point in enumerate(summary.exam_focus_points):
            _collect_ungrounded(
                issues,
                lecture_body,
                f"summary.exam_focus_points[{j}]",
                point,
            )

    if questions is not None:
        for i, eq in enumerate(questions.essay_questions):
            prefix = f"questions.essay_questions[{i}]"
            _collect_ungrounded(
                issues, lecture_body, f"{prefix}.question_text", eq.question_text
            )
            for j, concept in enumerate(eq.required_concepts):
                _collect_ungrounded(
                    issues,
                    lecture_body,
                    f"{prefix}.required_concepts[{j}]",
                    concept,
                )
            if eq.model_answer is not None:
                _collect_ungrounded(
                    issues,
                    lecture_body,
                    f"{prefix}.model_answer.answer_text",
                    eq.model_answer.answer_text,
                )
                for j, point in enumerate(eq.model_answer.key_points):
                    _collect_ungrounded(
                        issues,
                        lecture_body,
                        f"{prefix}.model_answer.key_points[{j}]",
                        point,
                    )

        for i, cq in enumerate(questions.calculation_questions):
            prefix = f"questions.calculation_questions[{i}]"
            _collect_ungrounded(
                issues, lecture_body, f"{prefix}.question_text", cq.question_text
            )
            for j, premise in enumerate(cq.premises):
                _collect_ungrounded(
                    issues, lecture_body, f"{prefix}.premises[{j}]", premise
                )
            for key, value in cq.variables.items():
                _collect_ungrounded(
                    issues, lecture_body, _variable_location(i, key), value
                )
            for j, step in enumerate(cq.calculation_steps):
                step_prefix = f"{prefix}.calculation_steps[{j}]"
                _collect_ungrounded(
                    issues, lecture_body, f"{step_prefix}.description", step.description
                )
                _collect_ungrounded(
                    issues, lecture_body, f"{step_prefix}.formula", step.formula
                )
                _collect_ungrounded(
                    issues,
                    lecture_body,
                    f"{step_prefix}.calculation",
                    step.calculation,
                )
                _collect_ungrounded(
                    issues, lecture_body, f"{step_prefix}.result", step.result
                )
            _collect_ungrounded(
                issues, lecture_body, f"{prefix}.final_answer", cq.final_answer
            )
            _collect_ungrounded(
                issues, lecture_body, f"{prefix}.verification", cq.verification
            )
            if cq.model_answer is not None:
                _collect_ungrounded(
                    issues,
                    lecture_body,
                    f"{prefix}.model_answer.answer_text",
                    cq.model_answer.answer_text,
                )
                for j, point in enumerate(cq.model_answer.key_points):
                    _collect_ungrounded(
                        issues,
                        lecture_body,
                        f"{prefix}.model_answer.key_points[{j}]",
                        point,
                    )

        for i, mc in enumerate(questions.multiple_choice_questions):
            prefix = f"questions.multiple_choice_questions[{i}]"
            _collect_ungrounded(
                issues, lecture_body, f"{prefix}.question_text", mc.question_text
            )
            for j, choice in enumerate(mc.choices):
                _collect_ungrounded(
                    issues, lecture_body, f"{prefix}.choices[{j}].text", choice.text
                )
                _collect_ungrounded(
                    issues,
                    lecture_body,
                    f"{prefix}.choices[{j}].explanation",
                    choice.explanation,
                )
            _collect_ungrounded(
                issues, lecture_body, f"{prefix}.explanation", mc.explanation
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

    def check_text_in_scope(text: str, location: str) -> ValidationIssue | None:
        """Helper to check if text content is within lecture scope."""
        text_words = set(text.lower().split())
        # Remove common words (English and Japanese)
        common = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "can", "and", "or",
            "but", "if", "then", "else", "when", "where", "what", "which",
            "who", "how", "this", "that", "these", "those", "it", "its",
            "を", "の", "が", "に", "は", "で", "と", "も", "へ", "から",
            "まで", "より", "など", "という", "こと", "もの", "ため",
        }
        text_words -= common

        # Check if at least some content words appear in lecture
        if len(text_words) > 3:
            matches = sum(1 for w in text_words if w in lecture_text_lower)
            if matches < len(text_words) * 0.3:
                return ValidationIssue(
                    category=IssueCategory.SCOPE_VIOLATION,
                    severity=IssueSeverity.WARNING,
                    message=f"Content may not be from lecture: '{text[:50]}...'",
                    location=location,
                    suggestion="Verify this content appears in lecture materials",
                )
        return None

    # Check each section's key points AND content
    for section in summary.sections:
        # Check key points
        for point in section.key_points:
            issue = check_text_in_scope(point, f"section: {section.heading}, key_point")
            if issue:
                issues.append(issue)

        # Check section content
        if section.content:
            issue = check_text_in_scope(section.content, f"section: {section.heading}, content")
            if issue:
                issues.append(issue)

    # Check exam_focus_points
    for point in summary.exam_focus_points:
        issue = check_text_in_scope(point, "exam_focus_points")
        if issue:
            issues.append(issue)

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
