"""Align Syllabus skill: Map lecture content to syllabus topics.

This skill checks that lecture content stays within syllabus scope
and identifies which topics are covered.

Input: LectureContent + Syllabus
Output: Alignment result with coverage map and violations
"""

from course_scribe.schemas.syllabus import Syllabus
from course_scribe.schemas.lecture import LectureContent


def align_with_syllabus(
    lecture: dict,
    syllabus: dict,
    strict_mode: bool = True,
) -> dict:
    """Align lecture content with syllabus.

    Args:
        lecture: LectureContent as dict
        syllabus: Syllabus as dict
        strict_mode: If True, flag content outside syllabus scope as violations

    Returns:
        dict containing:
        - covered_topics: Topics from syllabus that are covered
        - uncovered_topics: Topics from syllabus NOT covered
        - potential_violations: Content that may be outside scope
        - alignment_score: 0-1 score of how well aligned
        - week_match: Whether lecture matches its syllabus week
    """
    lecture_obj = LectureContent.model_validate(lecture)
    syllabus_obj = Syllabus.model_validate(syllabus)

    week_number = lecture_obj.week_number
    syllabus_week = syllabus_obj.get_week(week_number)

    result = {
        "week_number": week_number,
        "week_match": syllabus_week is not None,
        "covered_topics": [],
        "uncovered_topics": [],
        "potential_violations": [],
        "alignment_score": 0.0,
        "lecture_keywords": [],
        "syllabus_keywords": [],
    }

    if not syllabus_week:
        result["potential_violations"].append(
            f"Week {week_number} not found in syllabus"
        )
        return result

    # Get lecture content for matching
    lecture_text = lecture_obj.get_full_text().lower()
    lecture_keywords = {kw.lower() for kw in lecture_obj.get_all_keywords()}
    result["lecture_keywords"] = sorted(lecture_keywords)

    # Get syllabus scope for this week
    week_topics = set(syllabus_week.topics)
    week_keywords = set(syllabus_week.keywords)
    all_syllabus_keywords = syllabus_obj.get_all_keywords()

    result["syllabus_keywords"] = sorted(week_keywords)

    # Check topic coverage
    covered = []
    uncovered = []

    for topic in week_topics:
        topic_lower = topic.lower()
        # Check if topic appears in lecture content
        if topic_lower in lecture_text or _fuzzy_match(topic_lower, lecture_text):
            covered.append(topic)
        else:
            uncovered.append(topic)

    result["covered_topics"] = covered
    result["uncovered_topics"] = uncovered

    # Calculate alignment score
    if week_topics:
        result["alignment_score"] = len(covered) / len(week_topics)
    else:
        result["alignment_score"] = 1.0  # No topics to cover = fully aligned

    # Check for potential scope violations (strict mode)
    if strict_mode:
        violations = _detect_scope_violations(
            lecture_obj,
            syllabus_week,
            all_syllabus_keywords,
        )
        result["potential_violations"] = violations

    return result


def _fuzzy_match(topic: str, text: str) -> bool:
    """Check if topic words appear near each other in text."""
    words = topic.split()
    if len(words) == 1:
        return words[0] in text

    # Check if all words appear somewhere in text
    return all(word in text for word in words)


def _detect_scope_violations(
    lecture: LectureContent,
    syllabus_week,
    all_syllabus_keywords: set[str],
) -> list[str]:
    """Detect content that may be outside syllabus scope.

    This is a heuristic check - flags technical terms that:
    1. Appear prominently in the lecture
    2. Are NOT in this week's keywords
    3. Are NOT in any week's keywords (truly out of scope)
    """
    violations = []
    lecture_keywords = lecture.get_all_keywords()
    week_keywords_lower = {kw.lower() for kw in syllabus_week.keywords}
    all_keywords_lower = {kw.lower() for kw in all_syllabus_keywords}

    for kw in lecture_keywords:
        kw_lower = kw.lower()
        if kw_lower not in week_keywords_lower:
            if kw_lower not in all_keywords_lower:
                violations.append(
                    f"Term '{kw}' not found in any syllabus week - may be out of scope"
                )
            else:
                # Term exists but in different week - might be preview/review
                violations.append(
                    f"Term '{kw}' belongs to different week - verify if intentional"
                )

    return violations


def check_content_in_scope(
    content_text: str,
    syllabus: dict,
    week_number: int,
) -> dict:
    """Check if arbitrary content is within syllabus scope.

    Useful for validating generated summaries/questions.

    Args:
        content_text: Text content to check
        syllabus: Syllabus as dict
        week_number: Which week's scope to check against

    Returns:
        dict with in_scope (bool), violations (list), and confidence (float)
    """
    syllabus_obj = Syllabus.model_validate(syllabus)
    syllabus_week = syllabus_obj.get_week(week_number)

    if not syllabus_week:
        return {
            "in_scope": False,
            "violations": [f"Week {week_number} not in syllabus"],
            "confidence": 0.0,
        }

    content_lower = content_text.lower()
    week_topics = {t.lower() for t in syllabus_week.topics}
    week_keywords = {k.lower() for k in syllabus_week.keywords}
    all_keywords = {k.lower() for k in syllabus_obj.get_all_keywords()}

    # Extract technical terms from content
    from course_scribe.skills.ingest import _extract_keywords

    content_keywords = {k.lower() for k in _extract_keywords(content_text)}

    violations = []
    for kw in content_keywords:
        if kw not in week_keywords and kw not in all_keywords:
            if len(kw) > 3:  # Ignore very short terms
                violations.append(f"Term '{kw}' not in syllabus scope")

    # Calculate confidence
    in_scope_count = sum(1 for kw in content_keywords if kw in all_keywords)
    total_keywords = len(content_keywords) or 1
    confidence = in_scope_count / total_keywords

    return {
        "in_scope": len(violations) == 0 or confidence > 0.7,
        "violations": violations,
        "confidence": confidence,
    }
