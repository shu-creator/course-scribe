"""Lecture content schema definitions."""

from pydantic import BaseModel, Field


class LectureSection(BaseModel):
    """A section within a lecture."""

    heading: str = Field(default="", description="Section heading if any")
    content: str = Field(..., min_length=1, description="Section content text")
    keywords_mentioned: list[str] = Field(
        default_factory=list, description="Keywords mentioned in this section"
    )


class LectureContent(BaseModel):
    """Parsed lecture content from transcript or slides."""

    week_number: int = Field(..., ge=1, description="Week number this lecture belongs to")
    title: str = Field(default="", description="Lecture title if available")
    raw_text: str = Field(..., min_length=1, description="Full raw text content")
    sections: list[LectureSection] = Field(
        default_factory=list, description="Parsed sections"
    )
    source_type: str = Field(..., description="Source type: transcript, slides, etc.")
    source_filename: str = Field(default="", description="Original filename")

    def get_all_keywords(self) -> set[str]:
        """Get all keywords mentioned across all sections."""
        keywords = set()
        for section in self.sections:
            keywords.update(section.keywords_mentioned)
        return keywords

    def get_full_text(self) -> str:
        """Get combined text from all sections."""
        if self.sections:
            return "\n\n".join(s.content for s in self.sections)
        return self.raw_text
