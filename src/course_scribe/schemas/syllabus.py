"""Syllabus schema definitions."""

from pydantic import BaseModel, Field


class SyllabusWeek(BaseModel):
    """A single week/lecture entry in the syllabus."""

    week_number: int = Field(..., ge=1, description="Week number (1-indexed)")
    title: str = Field(..., min_length=1, description="Lecture title/topic")
    topics: list[str] = Field(default_factory=list, description="Key topics covered")
    keywords: list[str] = Field(default_factory=list, description="Important keywords/terms")
    learning_objectives: list[str] = Field(
        default_factory=list, description="Learning objectives for this week"
    )


class Syllabus(BaseModel):
    """Complete syllabus structure."""

    course_name: str = Field(..., min_length=1, description="Course name")
    instructor: str = Field(default="", description="Instructor name")
    description: str = Field(default="", description="Course description")
    weeks: list[SyllabusWeek] = Field(
        default_factory=list, description="Weekly lecture entries"
    )
    total_weeks: int = Field(default=0, ge=0, description="Total number of weeks")

    def get_week(self, week_number: int) -> SyllabusWeek | None:
        """Get a specific week's entry."""
        for week in self.weeks:
            if week.week_number == week_number:
                return week
        return None

    def get_all_topics(self) -> set[str]:
        """Get all topics across all weeks."""
        topics = set()
        for week in self.weeks:
            topics.update(week.topics)
        return topics

    def get_all_keywords(self) -> set[str]:
        """Get all keywords across all weeks."""
        keywords = set()
        for week in self.weeks:
            keywords.update(week.keywords)
        return keywords
