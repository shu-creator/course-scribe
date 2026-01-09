"""Generate Questions skill: Create exam questions from lecture content.

This skill generates essay, calculation, and multiple-choice questions
based on lecture content and syllabus alignment.

CRITICAL CONSTRAINTS:
- Questions must ONLY use content from the lecture
- Calculation questions must include: premises, variables, steps, units, verification
- All questions must map to specific syllabus topics

Input: LectureContent + Syllabus + StructuredSummary (optional)
Output: QuestionSet
"""

import re
import uuid
from course_scribe.core.types import QuestionType
from course_scribe.schemas.syllabus import Syllabus
from course_scribe.schemas.lecture import LectureContent
from course_scribe.schemas.questions import (
    QuestionSet,
    EssayQuestion,
    CalculationQuestion,
    CalculationStep,
    MultipleChoiceQuestion,
    Choice,
    ModelAnswer,
    GradingCriteria,
)


def generate_questions(
    lecture: dict,
    syllabus: dict,
    config: dict | None = None,
) -> dict:
    """Generate exam questions from lecture content.

    Args:
        lecture: LectureContent as dict
        syllabus: Syllabus as dict
        config: Optional configuration:
            - essay_count: Number of essay questions (default: 2)
            - calculation_count: Number of calculation questions (default: 1)
            - mc_count: Number of multiple choice questions (default: 3)
            - difficulty: "easy", "medium", "hard" (default: "medium")

    Returns:
        QuestionSet as dict

    Note:
        This MVP generates TEMPLATE questions that demonstrate the structure.
        Production version would use LLM for actual question generation.
    """
    config = config or {}
    essay_count = config.get("essay_count", 2)
    calc_count = config.get("calculation_count", 1)
    mc_count = config.get("mc_count", 3)
    difficulty = config.get("difficulty", "medium")

    lecture_obj = LectureContent.model_validate(lecture)
    syllabus_obj = Syllabus.model_validate(syllabus)

    week_number = lecture_obj.week_number
    syllabus_week = syllabus_obj.get_week(week_number)

    # Extract topics and keywords for question generation
    topics = syllabus_week.topics if syllabus_week else []
    keywords = syllabus_week.keywords if syllabus_week else []

    # Generate questions
    essay_questions = _generate_essay_questions(
        lecture_obj, topics, keywords, essay_count, difficulty
    )
    calc_questions = _generate_calculation_questions(
        lecture_obj, topics, keywords, calc_count, difficulty
    )
    mc_questions = _generate_mc_questions(
        lecture_obj, topics, keywords, mc_count, difficulty
    )

    question_set = QuestionSet(
        week_number=week_number,
        title=f"Week {week_number} Exam Questions",
        essay_questions=essay_questions,
        calculation_questions=calc_questions,
        multiple_choice_questions=mc_questions,
    )

    return question_set.model_dump()


def _generate_question_id() -> str:
    """Generate a unique question ID."""
    return f"q_{uuid.uuid4().hex[:8]}"


def _generate_essay_questions(
    lecture: LectureContent,
    topics: list[str],
    keywords: list[str],
    count: int,
    difficulty: str,
) -> list[EssayQuestion]:
    """Generate essay questions (論述問題).

    Essay questions should:
    - Ask for explanation/analysis of concepts
    - Require understanding, not just memorization
    - Map to specific syllabus topics
    """
    questions = []

    # Generate questions based on topics
    for i, topic in enumerate(topics[:count]):
        # Find relevant content from lecture
        relevant_content = _find_relevant_content(lecture, topic)

        question = EssayQuestion(
            question_id=_generate_question_id(),
            question_type=QuestionType.ESSAY,
            question_text=f"「{topic}」について、講義で扱われた内容に基づいて説明しなさい。",
            syllabus_topics=[topic],
            difficulty=difficulty,
            source_reference=f"Lecture {lecture.week_number}",
            expected_length="400-600字程度",
            required_concepts=_extract_concepts_from_content(relevant_content, keywords),
            model_answer=ModelAnswer(
                answer_text=f"[模範解答: {topic}についての説明。講義内容から{relevant_content[:100]}...]",
                key_points=[
                    f"{topic}の定義を正確に述べること",
                    "具体例を講義内容から挙げること",
                    "関連概念との関係を説明すること",
                ],
                grading=GradingCriteria(
                    full_marks=20,
                    criteria=[
                        f"{topic}の定義が正確（5点）",
                        "講義内容に基づいた説明（8点）",
                        "論理的な構成（4点）",
                        "適切な具体例（3点）",
                    ],
                    partial_credit_rules=[
                        "定義のみ正確な場合は5点",
                        "具体例が不適切な場合は-2点",
                        "講義外の内容を含む場合は減点対象",
                    ],
                    common_mistakes=[
                        "定義を曖昧に述べる",
                        "講義で扱っていない内容を含める",
                        "具体例なしに抽象論のみで終わる",
                    ],
                ),
            ),
        )
        questions.append(question)

    return questions


def _generate_calculation_questions(
    lecture: LectureContent,
    topics: list[str],
    keywords: list[str],
    count: int,
    difficulty: str,
) -> list[CalculationQuestion]:
    """Generate calculation questions (計算問題).

    CRITICAL: Calculation questions MUST include:
    - Clear premises and given conditions
    - Variable definitions with units
    - Step-by-step solution
    - Final answer with units
    - Verification/sanity check
    """
    questions = []

    # Check if lecture contains numerical/calculation content
    has_calculations = _detect_calculation_content(lecture)

    if not has_calculations:
        # Return empty if no calculation content in lecture
        return questions

    for i in range(min(count, 1)):  # Limit to 1 for MVP
        question = CalculationQuestion(
            question_id=_generate_question_id(),
            question_type=QuestionType.CALCULATION,
            question_text="[計算問題: 講義内容に基づいた計算を求める問題]",
            syllabus_topics=topics[:2] if topics else [],
            difficulty=difficulty,
            source_reference=f"Lecture {lecture.week_number}",
            premises=[
                "[前提条件1: 与えられた値や条件]",
                "[前提条件2: 追加の条件]",
            ],
            variables={
                "x": "[変数の説明と単位]",
                "y": "[変数の説明と単位]",
            },
            calculation_steps=[
                CalculationStep(
                    step_number=1,
                    description="[手順1の説明]",
                    formula="[使用する公式]",
                    calculation="[具体的な計算]",
                    result="[結果と単位]",
                ),
                CalculationStep(
                    step_number=2,
                    description="[手順2の説明]",
                    formula="[使用する公式]",
                    calculation="[具体的な計算]",
                    result="[結果と単位]",
                ),
            ],
            final_answer="[最終回答と単位]",
            verification="[検算: 結果の妥当性確認方法]",
            model_answer=ModelAnswer(
                answer_text="[詳細な解答手順]",
                key_points=[
                    "公式を正しく適用すること",
                    "単位を明記すること",
                    "検算を行うこと",
                ],
                grading=GradingCriteria(
                    full_marks=25,
                    criteria=[
                        "正しい公式の選択（5点）",
                        "計算過程が正確（10点）",
                        "単位の記載（3点）",
                        "最終解答が正確（5点）",
                        "検算の実施（2点）",
                    ],
                    partial_credit_rules=[
                        "公式は正しいが計算ミスの場合は-5点",
                        "単位の記載漏れは-3点",
                        "途中式のみ正解の場合は部分点",
                    ],
                    common_mistakes=[
                        "単位の換算ミス",
                        "公式の適用条件を確認しない",
                        "有効数字の処理が不適切",
                    ],
                ),
            ),
        )
        questions.append(question)

    return questions


def _generate_mc_questions(
    lecture: LectureContent,
    topics: list[str],
    keywords: list[str],
    count: int,
    difficulty: str,
) -> list[MultipleChoiceQuestion]:
    """Generate multiple choice questions (選択問題).

    Multiple choice questions should:
    - Test understanding of key concepts
    - Have plausible distractors
    - Have clear correct answer with explanation
    """
    questions = []

    for i, keyword in enumerate(keywords[:count]):
        # Create question about the keyword
        question = MultipleChoiceQuestion(
            question_id=_generate_question_id(),
            question_type=QuestionType.MULTIPLE_CHOICE,
            question_text=f"「{keyword}」について、正しい記述を選びなさい。",
            syllabus_topics=topics[:1] if topics else [],
            difficulty=difficulty,
            source_reference=f"Lecture {lecture.week_number}",
            choices=[
                Choice(
                    label="a",
                    text=f"[{keyword}についての正しい記述]",
                    is_correct=True,
                    explanation="講義で説明された通り",
                ),
                Choice(
                    label="b",
                    text=f"[{keyword}についての誤った記述1]",
                    is_correct=False,
                    explanation="[なぜ誤りかの説明]",
                ),
                Choice(
                    label="c",
                    text=f"[{keyword}についての誤った記述2]",
                    is_correct=False,
                    explanation="[なぜ誤りかの説明]",
                ),
                Choice(
                    label="d",
                    text=f"[{keyword}についての誤った記述3]",
                    is_correct=False,
                    explanation="[なぜ誤りかの説明]",
                ),
            ],
            correct_answer="a",
            explanation=f"講義では{keyword}について[正しい内容]と説明されています。",
        )
        questions.append(question)

    return questions


def _find_relevant_content(lecture: LectureContent, topic: str) -> str:
    """Find lecture content relevant to a topic."""
    topic_lower = topic.lower()

    for section in lecture.sections:
        if topic_lower in section.content.lower():
            return section.content[:500]

    # Fallback to raw text search
    text = lecture.raw_text.lower()
    idx = text.find(topic_lower)
    if idx != -1:
        start = max(0, idx - 100)
        end = min(len(text), idx + 400)
        return lecture.raw_text[start:end]

    return lecture.raw_text[:500]


def _extract_concepts_from_content(content: str, keywords: list[str]) -> list[str]:
    """Extract concepts mentioned in content that match keywords."""
    concepts = []
    content_lower = content.lower()

    for keyword in keywords:
        if keyword.lower() in content_lower:
            concepts.append(keyword)

    return concepts[:5]


def _detect_calculation_content(lecture: LectureContent) -> bool:
    """Detect if lecture contains calculation-related content."""
    indicators = [
        "計算", "公式", "=", "∑", "∫", "solve", "calculate",
        "formula", "equation", "結果", "単位",
    ]

    text = lecture.raw_text.lower()
    return any(ind.lower() in text for ind in indicators)


def create_question_template(
    question_type: str,
    topic: str,
    week_number: int,
) -> dict:
    """Create an empty question template for manual filling.

    Useful for LLM prompting or manual question creation.
    """
    if question_type == "essay":
        return EssayQuestion(
            question_id=_generate_question_id(),
            question_type=QuestionType.ESSAY,
            question_text=f"[{topic}についての論述問題]",
            syllabus_topics=[topic],
            difficulty="medium",
            source_reference=f"Lecture {week_number}",
            expected_length="400-600字",
            required_concepts=[],
            model_answer=None,
        ).model_dump()

    elif question_type == "calculation":
        return CalculationQuestion(
            question_id=_generate_question_id(),
            question_type=QuestionType.CALCULATION,
            question_text="[計算問題]",
            syllabus_topics=[topic],
            difficulty="medium",
            source_reference=f"Lecture {week_number}",
            premises=["[前提条件]"],
            variables={},
            calculation_steps=[],
            final_answer="[答えと単位]",
            verification="[検算]",
            model_answer=None,
        ).model_dump()

    else:  # multiple_choice
        return MultipleChoiceQuestion(
            question_id=_generate_question_id(),
            question_type=QuestionType.MULTIPLE_CHOICE,
            question_text=f"[{topic}についての選択問題]",
            syllabus_topics=[topic],
            difficulty="medium",
            source_reference=f"Lecture {week_number}",
            choices=[
                Choice(label="a", text="[選択肢a]", is_correct=False, explanation=""),
                Choice(label="b", text="[選択肢b]", is_correct=False, explanation=""),
                Choice(label="c", text="[選択肢c]", is_correct=False, explanation=""),
                Choice(label="d", text="[選択肢d]", is_correct=False, explanation=""),
            ],
            correct_answer="a",
            explanation="",
        ).model_dump()
