"""Question and answer schema definitions."""

from pydantic import BaseModel, Field
from course_scribe.core.types import QuestionType


class GradingCriteria(BaseModel):
    """Grading criteria for a question."""

    full_marks: int = Field(..., ge=1, description="Full marks for this question")
    criteria: list[str] = Field(
        default_factory=list, description="Grading criteria points"
    )
    partial_credit_rules: list[str] = Field(
        default_factory=list, description="Rules for partial credit"
    )
    common_mistakes: list[str] = Field(
        default_factory=list, description="Common mistakes to watch for"
    )


class ModelAnswer(BaseModel):
    """Model answer for a question."""

    answer_text: str = Field(..., min_length=1, description="Full model answer")
    key_points: list[str] = Field(
        default_factory=list, description="Key points that must be included"
    )
    grading: GradingCriteria = Field(..., description="Grading criteria")


class Question(BaseModel):
    """Base question model."""

    question_id: str = Field(..., description="Unique question identifier")
    question_type: QuestionType = Field(..., description="Type of question")
    question_text: str = Field(..., min_length=1, description="Question text")
    syllabus_topics: list[str] = Field(
        default_factory=list, description="Syllabus topics this question covers"
    )
    difficulty: str = Field(
        default="medium", description="Difficulty: easy, medium, hard"
    )
    source_reference: str = Field(
        default="", description="Reference to lecture content source"
    )


class EssayQuestion(Question):
    """Essay/discussion question (論述問題)."""

    question_type: QuestionType = Field(default=QuestionType.ESSAY)
    expected_length: str = Field(
        default="", description="Expected answer length guidance"
    )
    required_concepts: list[str] = Field(
        default_factory=list, description="Concepts that must be discussed"
    )
    model_answer: ModelAnswer | None = Field(default=None, description="Model answer")


class CalculationStep(BaseModel):
    """A single step in a calculation."""

    step_number: int = Field(..., ge=1, description="Step number")
    description: str = Field(..., description="What this step does")
    formula: str = Field(default="", description="Formula used")
    calculation: str = Field(..., description="Actual calculation")
    result: str = Field(..., description="Result with units")


class CalculationQuestion(Question):
    """Calculation problem (計算問題)."""

    question_type: QuestionType = Field(default=QuestionType.CALCULATION)
    premises: list[str] = Field(
        ..., min_length=1, description="Given premises/conditions"
    )
    variables: dict[str, str] = Field(
        default_factory=dict,
        description="Variable definitions with units (e.g., {'v': 'velocity (m/s)'})",
    )
    calculation_steps: list[CalculationStep] = Field(
        default_factory=list, description="Step-by-step solution"
    )
    final_answer: str = Field(..., description="Final answer with units")
    verification: str = Field(
        default="", description="Verification/sanity check of the answer"
    )
    model_answer: ModelAnswer | None = Field(default=None, description="Model answer")


class Choice(BaseModel):
    """A choice in a multiple choice question."""

    label: str = Field(..., description="Choice label (a, b, c, d)")
    text: str = Field(..., min_length=1, description="Choice text")
    is_correct: bool = Field(default=False, description="Whether this is correct")
    explanation: str = Field(
        default="", description="Explanation for why correct/incorrect"
    )


class MultipleChoiceQuestion(Question):
    """Multiple choice question (選択問題)."""

    question_type: QuestionType = Field(default=QuestionType.MULTIPLE_CHOICE)
    choices: list[Choice] = Field(..., min_length=2, description="Answer choices")
    correct_answer: str = Field(..., description="Correct choice label")
    explanation: str = Field(default="", description="Explanation of correct answer")


class QuestionSet(BaseModel):
    """A set of questions for a lecture."""

    week_number: int = Field(..., ge=1, description="Week number")
    title: str = Field(default="", description="Question set title")
    essay_questions: list[EssayQuestion] = Field(
        default_factory=list, description="Essay questions"
    )
    calculation_questions: list[CalculationQuestion] = Field(
        default_factory=list, description="Calculation questions"
    )
    multiple_choice_questions: list[MultipleChoiceQuestion] = Field(
        default_factory=list, description="Multiple choice questions"
    )

    def all_questions(self) -> list[Question]:
        """Get all questions as a flat list."""
        return (
            list(self.essay_questions)
            + list(self.calculation_questions)
            + list(self.multiple_choice_questions)
        )

    def to_json_dict(self) -> dict:
        """Export as JSON-serializable dict."""
        return self.model_dump(mode="json")
