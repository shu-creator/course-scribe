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


# System prompt for summary generation
SUMMARY_SYSTEM_PROMPT = """あなたは大学の講義内容を構造化要約する専門家です。

重要な制約:
1. 要約は必ず講義内容のみに基づくこと。外部知識や推測は禁止。
2. シラバスで指定されたトピックに沿って構造化すること。
3. 試験対策として使える形式で出力すること。
4. 定義、公式、重要概念は正確に記載すること。

出力形式: JSON
"""


def summarize_lecture(
    lecture: dict,
    syllabus: dict,
    alignment: dict | None = None,
    use_llm: bool = False,
    llm_provider: str = "claude",
) -> dict:
    """Generate a structured summary from lecture content.

    Args:
        lecture: LectureContent as dict
        syllabus: Syllabus as dict
        alignment: Optional pre-computed alignment result
        use_llm: If True, use LLM for intelligent summarization
        llm_provider: LLM provider to use (default: "claude")

    Returns:
        StructuredSummary as dict

    Note:
        When use_llm=False (default), generates a template/heuristic summary.
        When use_llm=True, uses Claude API for intelligent summarization.
    """
    lecture_obj = LectureContent.model_validate(lecture)
    syllabus_obj = Syllabus.model_validate(syllabus)

    # Use LLM for intelligent summarization
    if use_llm:
        return _summarize_with_llm(lecture_obj, syllabus_obj, alignment, llm_provider)

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


def _summarize_with_llm(
    lecture: LectureContent,
    syllabus: Syllabus,
    alignment: dict | None,
    provider_name: str,
) -> dict:
    """Generate summary using LLM.

    Args:
        lecture: Parsed lecture content
        syllabus: Parsed syllabus
        alignment: Optional alignment result
        provider_name: LLM provider to use

    Returns:
        StructuredSummary as dict
    """
    from course_scribe.llm import get_provider

    provider = get_provider(provider_name)
    syllabus_week = syllabus.get_week(lecture.week_number)

    # Build the prompt
    prompt = _build_summary_prompt(lecture, syllabus_week, alignment)

    # Generate summary using LLM
    result = provider.generate_json(
        prompt=prompt,
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        max_tokens=4096,
    )

    # Validate and fill in missing fields
    week_number = lecture.week_number

    # Ensure required fields exist
    if "week_number" not in result:
        result["week_number"] = week_number
    if "title" not in result:
        result["title"] = lecture.title or f"Week {week_number} Summary"
    if "sections" not in result:
        result["sections"] = []
    if "syllabus_alignment" not in result:
        result["syllabus_alignment"] = {}
    if "exam_focus_points" not in result:
        result["exam_focus_points"] = []
    if "uncovered_topics" not in result:
        result["uncovered_topics"] = alignment.get("uncovered_topics", []) if alignment else []

    # Validate through Pydantic
    summary = StructuredSummary.model_validate(result)
    return summary.model_dump()


def _build_summary_prompt(
    lecture: LectureContent,
    syllabus_week,
    alignment: dict | None,
) -> str:
    """Build the prompt for summary generation."""
    parts = []

    # Lecture content
    parts.append("# 講義内容")
    parts.append(f"タイトル: {lecture.title}")
    parts.append(f"Week: {lecture.week_number}")
    parts.append("")
    parts.append(lecture.get_full_text())
    parts.append("")

    # Syllabus context
    if syllabus_week:
        parts.append("# シラバス情報（この週）")
        parts.append(f"テーマ: {syllabus_week.title}")
        parts.append(f"トピック: {', '.join(syllabus_week.topics)}")
        parts.append(f"キーワード: {', '.join(syllabus_week.keywords)}")
        parts.append("")

    # Alignment info
    if alignment:
        if alignment.get("uncovered_topics"):
            parts.append(f"注意: 以下のトピックは講義でカバーされていません: {alignment['uncovered_topics']}")
        parts.append("")

    # Output format specification
    parts.append("# 出力形式")
    parts.append("""
以下のJSON形式で構造化要約を生成してください:

{
  "week_number": <週番号>,
  "title": "<要約タイトル>",
  "syllabus_alignment": {
    "<トピック名>": true/false,  // 講義でカバーされたか
    ...
  },
  "sections": [
    {
      "heading": "<セクション見出し>",
      "content": "<要約内容（Markdown形式）>",
      "syllabus_topics": ["<関連トピック>"],
      "key_points": ["<重要ポイント1>", "<重要ポイント2>"]
    }
  ],
  "exam_focus_points": ["<試験で重要なポイント1>", ...],
  "uncovered_topics": ["<カバーされていないトピック>", ...]
}

重要:
- 講義内容に書かれていることのみを要約すること
- 外部知識や推測を加えないこと
- 定義や公式は正確に記載すること
- 試験対策に役立つ形式で整理すること
""")

    return "\n".join(parts)
