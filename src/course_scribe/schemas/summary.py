"""Structured summary schema definitions."""

from pydantic import BaseModel, Field


class SummarySection(BaseModel):
    """A section in the structured summary."""

    heading: str = Field(..., min_length=1, description="Section heading")
    content: str = Field(..., min_length=1, description="Section content in markdown")
    syllabus_topics: list[str] = Field(
        default_factory=list,
        description="Syllabus topics this section addresses",
    )
    key_points: list[str] = Field(
        default_factory=list, description="Key points for exam preparation"
    )


class StructuredSummary(BaseModel):
    """Structured summary aligned with syllabus."""

    week_number: int = Field(..., ge=1, description="Week number")
    title: str = Field(..., min_length=1, description="Summary title")
    syllabus_alignment: dict[str, bool] = Field(
        default_factory=dict,
        description="Map of syllabus topics to whether they're covered",
    )
    sections: list[SummarySection] = Field(
        default_factory=list, description="Summary sections"
    )
    exam_focus_points: list[str] = Field(
        default_factory=list, description="Points likely to appear in exams"
    )
    uncovered_topics: list[str] = Field(
        default_factory=list,
        description="Syllabus topics NOT covered in this lecture",
    )

    def to_markdown(self) -> str:
        """Export summary as markdown."""
        lines = [f"# {self.title}", f"**Week {self.week_number}**", ""]

        if self.exam_focus_points:
            lines.append("## Exam Focus Points")
            for point in self.exam_focus_points:
                lines.append(f"- {point}")
            lines.append("")

        for section in self.sections:
            lines.append(f"## {section.heading}")
            lines.append(section.content)
            if section.key_points:
                lines.append("")
                lines.append("**Key Points:**")
                for point in section.key_points:
                    lines.append(f"- {point}")
            lines.append("")

        if self.uncovered_topics:
            lines.append("## Topics Not Covered in This Lecture")
            lines.append(
                "*These topics are in the syllabus but were not addressed:*"
            )
            for topic in self.uncovered_topics:
                lines.append(f"- {topic}")

        return "\n".join(lines)
