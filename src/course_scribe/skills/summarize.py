"""Summarize skill: Generate structured summaries from lecture content.

This skill creates exam-oriented summaries aligned with syllabus topics.

IMPORTANT: Summaries must ONLY include content from the lecture.
No external knowledge or interpolation allowed.

Input: LectureContent + Syllabus + alignment result
Output: StructuredSummary
"""

from course_scribe.schemas.syllabus import Syllabus
from course_scribe.schemas.lecture import LectureContent
from course_scribe.schemas.summary import StructuredSummary, SummarySection


def summarize_lecture(
    lecture: dict,
    syllabus: dict,
    alignment: dict | None = None,
) -> dict:
    """Generate a structured summary from lecture content.

    Args:
        lecture: LectureContent as dict
        syllabus: Syllabus as dict
        alignment: Optional pre-computed alignment result

    Returns:
        StructuredSummary as dict

    Note:
        This function provides the STRUCTURE for summaries.
        Actual content generation requires an LLM - this MVP version
        creates a template that can be filled in or demonstrates
        the expected output format.
    """
    lecture_obj = LectureContent.model_validate(lecture)
    syllabus_obj = Syllabus.model_validate(syllabus)

    week_number = lecture_obj.week_number
    syllabus_week = syllabus_obj.get_week(week_number)

    # Build syllabus alignment map
    syllabus_alignment = {}
    if syllabus_week:
        for topic in syllabus_week.topics:
            # Check if topic is covered in lecture
            topic_lower = topic.lower()
            is_covered = topic_lower in lecture_obj.raw_text.lower()
            syllabus_alignment[topic] = is_covered

    # Create sections from lecture sections
    sections = []
    for lecture_section in lecture_obj.sections:
        # Identify which syllabus topics this section covers
        covered_topics = []
        if syllabus_week:
            for topic in syllabus_week.topics:
                if topic.lower() in lecture_section.content.lower():
                    covered_topics.append(topic)

        # Extract key points (sentences with keywords)
        key_points = _extract_key_points(
            lecture_section.content, lecture_section.keywords_mentioned
        )

        sections.append(
            SummarySection(
                heading=lecture_section.heading or "Main Content",
                content=_create_summary_content(lecture_section.content),
                syllabus_topics=covered_topics,
                key_points=key_points,
            )
        )

    # Identify exam focus points
    exam_focus = _identify_exam_focus(lecture_obj, syllabus_week)

    # Identify uncovered topics
    uncovered = []
    if alignment and "uncovered_topics" in alignment:
        uncovered = alignment["uncovered_topics"]
    elif syllabus_week:
        uncovered = [
            topic
            for topic, covered in syllabus_alignment.items()
            if not covered
        ]

    summary = StructuredSummary(
        week_number=week_number,
        title=lecture_obj.title or f"Week {week_number} Summary",
        syllabus_alignment=syllabus_alignment,
        sections=sections,
        exam_focus_points=exam_focus,
        uncovered_topics=uncovered,
    )

    return summary.model_dump()


def _create_summary_content(content: str) -> str:
    """Create summary content from raw lecture content.

    MVP version: Returns structured version of original content.
    Production version: Would use LLM to generate concise summary.
    """
    # Simple paragraph-based summarization
    paragraphs = content.split("\n\n")
    if len(paragraphs) <= 3:
        return content.strip()

    # Take first sentence of each paragraph as summary
    summary_parts = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Get first sentence
        sentences = para.replace("。", ".").split(".")
        if sentences and sentences[0].strip():
            summary_parts.append(sentences[0].strip() + ".")

    return "\n\n".join(summary_parts[:5])  # Limit to 5 key sentences


def _extract_key_points(content: str, keywords: list[str]) -> list[str]:
    """Extract key points from content based on keywords."""
    key_points = []
    sentences = content.replace("。", ".").replace("\n", " ").split(".")

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # Check if sentence contains any keywords
        for keyword in keywords:
            if keyword.lower() in sentence.lower():
                # Clean up and add
                point = sentence.strip()
                if len(point) > 10 and point not in key_points:
                    key_points.append(point)
                break

    return key_points[:5]  # Limit to 5 key points


def _identify_exam_focus(lecture: LectureContent, syllabus_week) -> list[str]:
    """Identify points likely to appear in exams.

    Heuristic: Focus on content that:
    - Contains syllabus keywords
    - Has definitions or explanations
    - Contains formulas or calculations
    - Is emphasized (bold, repeated)
    """
    focus_points = []

    # Keywords from syllabus are likely exam topics
    if syllabus_week:
        for keyword in syllabus_week.keywords[:5]:  # Top 5 keywords
            if keyword.lower() in lecture.raw_text.lower():
                focus_points.append(f"Understand: {keyword}")

    # Look for definitions
    for section in lecture.sections:
        content = section.content.lower()
        # Common definition patterns
        if "とは" in content or " is " in content or "defined as" in content:
            focus_points.append(f"Definition in: {section.heading or 'lecture'}")
            break

    # Look for formulas/calculations
    if any(c in lecture.raw_text for c in ["=", "∑", "∫", "×", "÷"]):
        focus_points.append("Contains formulas - review calculation steps")

    return focus_points[:7]  # Limit exam focus points


def generate_summary_template(
    syllabus: dict,
    week_number: int,
) -> dict:
    """Generate an empty summary template based on syllabus.

    Useful for manual summary creation or LLM prompting.
    """
    syllabus_obj = Syllabus.model_validate(syllabus)
    syllabus_week = syllabus_obj.get_week(week_number)

    if not syllabus_week:
        return {"error": f"Week {week_number} not found in syllabus"}

    # Create template sections from syllabus topics
    sections = []
    for topic in syllabus_week.topics:
        sections.append(
            SummarySection(
                heading=topic,
                content=f"[Summary of {topic} from lecture]",
                syllabus_topics=[topic],
                key_points=[
                    f"[Key point 1 about {topic}]",
                    f"[Key point 2 about {topic}]",
                ],
            )
        )

    template = StructuredSummary(
        week_number=week_number,
        title=syllabus_week.title,
        syllabus_alignment={topic: False for topic in syllabus_week.topics},
        sections=sections,
        exam_focus_points=[f"[Focus: {kw}]" for kw in syllabus_week.keywords[:5]],
        uncovered_topics=[],
    )

    return template.model_dump()
