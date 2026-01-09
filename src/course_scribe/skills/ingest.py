"""Ingest skill: Parse documents into structured format.

This skill converts raw document content (PDF, Markdown, Text) into
structured LectureContent or Syllabus objects.

Input: Raw text content + metadata
Output: LectureContent or Syllabus schema
"""

import re
from course_scribe.schemas.syllabus import Syllabus, SyllabusWeek
from course_scribe.schemas.lecture import LectureContent, LectureSection


def ingest_document(
    content: str,
    document_type: str,
    source_filename: str = "",
    week_number: int | None = None,
    is_syllabus: bool = False,
) -> dict:
    """Ingest a document and return structured data.

    Args:
        content: Raw text content of the document
        document_type: Type of document (pdf, md, txt)
        source_filename: Original filename for reference
        week_number: Week number for lecture content (required if not syllabus)
        is_syllabus: Whether this is a syllabus document

    Returns:
        dict: Structured data as Syllabus or LectureContent schema
    """
    if is_syllabus:
        return _parse_syllabus(content, source_filename).model_dump()
    else:
        if week_number is None:
            # Try to extract week number from filename
            week_number = _extract_week_number(source_filename) or 1
        return _parse_lecture(
            content, document_type, source_filename, week_number
        ).model_dump()


def _extract_week_number(filename: str) -> int | None:
    """Extract week number from filename like 'lecture_03.txt'."""
    match = re.search(r"(\d+)", filename)
    if match:
        return int(match.group(1))
    return None


def _parse_syllabus(content: str, source_filename: str) -> Syllabus:
    """Parse syllabus content into structured format.

    Assumption: Syllabus has sections marked by week/lecture numbers
    and contains topics/keywords for each week.
    """
    lines = content.strip().split("\n")
    course_name = ""
    instructor = ""
    description = ""
    weeks: list[SyllabusWeek] = []

    current_week: dict | None = None
    current_section = "header"

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect course name (usually first heading)
        if not course_name and (line.startswith("#") or line.isupper()):
            course_name = line.lstrip("#").strip()
            continue

        # Detect instructor
        if "instructor" in line.lower() or "教員" in line or "担当" in line:
            instructor = re.sub(r".*[:：]\s*", "", line)
            continue

        # Detect week/lecture headers
        week_match = re.search(
            r"(?:week|第|lecture|回)\s*(\d+)", line, re.IGNORECASE
        )
        if week_match:
            # Save previous week if exists
            if current_week:
                weeks.append(SyllabusWeek(**current_week))

            week_num = int(week_match.group(1))
            # Extract title (text after week number)
            title = re.sub(r"(?:week|第|lecture|回)\s*\d+\s*[:：]?\s*", "", line, flags=re.IGNORECASE)
            current_week = {
                "week_number": week_num,
                "title": title or f"Week {week_num}",
                "topics": [],
                "keywords": [],
                "learning_objectives": [],
            }
            current_section = "topics"
            continue

        # Collect content under current week
        if current_week:
            # Detect section markers
            if any(kw in line.lower() for kw in ["keyword", "キーワード", "用語"]):
                current_section = "keywords"
                continue
            if any(kw in line.lower() for kw in ["objective", "目標", "到達目標"]):
                current_section = "objectives"
                continue
            if any(kw in line.lower() for kw in ["topic", "トピック", "内容"]):
                current_section = "topics"
                continue

            # Add to appropriate list
            item = line.lstrip("-*•").strip()
            if item:
                if current_section == "keywords":
                    current_week["keywords"].append(item)
                elif current_section == "objectives":
                    current_week["learning_objectives"].append(item)
                else:
                    current_week["topics"].append(item)
        else:
            # Collect description before first week
            if description:
                description += " " + line
            else:
                description = line

    # Don't forget the last week
    if current_week:
        weeks.append(SyllabusWeek(**current_week))

    return Syllabus(
        course_name=course_name or "Unknown Course",
        instructor=instructor,
        description=description,
        weeks=weeks,
        total_weeks=len(weeks),
    )


def _parse_lecture(
    content: str, document_type: str, source_filename: str, week_number: int
) -> LectureContent:
    """Parse lecture content into structured format.

    Assumption: Content may have headers (markdown-style or numbered)
    that indicate sections.
    """
    lines = content.strip().split("\n")
    sections: list[LectureSection] = []
    title = ""

    current_section: dict | None = None
    current_content_lines: list[str] = []

    for line in lines:
        # Detect title (first heading)
        if not title and (line.startswith("#") or (line and line[0].isdigit() and "." in line[:5])):
            title = line.lstrip("#").lstrip("0123456789.").strip()
            continue

        # Detect section headers
        is_header = (
            line.startswith("##")
            or line.startswith("###")
            or re.match(r"^\d+\.\s+\w", line)
            or (line.isupper() and len(line) > 3)
        )

        if is_header:
            # Save previous section
            if current_content_lines:
                section_content = "\n".join(current_content_lines).strip()
                if section_content:
                    heading = current_section["heading"] if current_section else ""
                    sections.append(
                        LectureSection(
                            heading=heading,
                            content=section_content,
                            keywords_mentioned=_extract_keywords(section_content),
                        )
                    )
                current_content_lines = []

            # Start new section
            heading = line.lstrip("#").lstrip("0123456789.").strip()
            current_section = {"heading": heading}
        else:
            current_content_lines.append(line)

    # Don't forget the last section
    if current_content_lines:
        section_content = "\n".join(current_content_lines).strip()
        if section_content:
            heading = current_section["heading"] if current_section else ""
            sections.append(
                LectureSection(
                    heading=heading,
                    content=section_content,
                    keywords_mentioned=_extract_keywords(section_content),
                )
            )

    # If no sections were detected, create one section with all content
    if not sections:
        sections.append(
            LectureSection(
                heading="",
                content=content.strip(),
                keywords_mentioned=_extract_keywords(content),
            )
        )

    return LectureContent(
        week_number=week_number,
        title=title or f"Lecture {week_number}",
        raw_text=content,
        sections=sections,
        source_type=document_type,
        source_filename=source_filename,
    )


def _extract_keywords(text: str) -> list[str]:
    """Extract potential keywords from text.

    This is a simple heuristic - looks for:
    - Text in bold/emphasis (markdown)
    - Text in quotes
    - CamelCase or UPPERCASE terms
    - Japanese katakana terms (often technical terms)
    """
    keywords = set()

    # Bold/emphasis in markdown
    for match in re.finditer(r"\*\*([^*]+)\*\*|\*([^*]+)\*|__([^_]+)__|_([^_]+)_", text):
        kw = match.group(1) or match.group(2) or match.group(3) or match.group(4)
        if kw and len(kw) > 1:
            keywords.add(kw.strip())

    # Quoted terms
    for match in re.finditer(r"[「「]([^」」]+)[」」]|\"([^\"]+)\"", text):
        kw = match.group(1) or match.group(2)
        if kw and len(kw) > 1:
            keywords.add(kw.strip())

    # CamelCase (likely technical terms)
    for match in re.finditer(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", text):
        keywords.add(match.group(1))

    # UPPERCASE terms (acronyms, etc.)
    for match in re.finditer(r"\b([A-Z]{2,})\b", text):
        keywords.add(match.group(1))

    return sorted(keywords)
