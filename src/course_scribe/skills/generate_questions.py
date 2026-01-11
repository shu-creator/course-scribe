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


# System prompt for question generation
QUESTION_SYSTEM_PROMPT = """あなたは大学の試験問題を作成する専門家です。

重要な制約:
1. 問題は必ず講義内容のみに基づくこと。外部知識を前提としない。
2. 論述問題: 明確な採点基準と模範解答を含める
3. 計算問題: 前提条件、変数定義、計算手順、単位、検算を必ず含める
4. 選択問題: 4つの選択肢、正解1つ、各選択肢の解説を含める
5. シラバスのトピック・キーワードに対応する問題を生成すること

出力形式: JSON
"""


def generate_questions(
    lecture: dict,
    syllabus: dict,
    config: dict | None = None,
    use_llm: bool = False,
    llm_provider: str = "claude",
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
        use_llm: If True, use LLM for question generation
        llm_provider: LLM provider to use (default: "claude")

    Returns:
        QuestionSet as dict

    Note:
        When use_llm=False (default), generates template questions.
        When use_llm=True, uses Claude API for intelligent question generation.
    """
    config = config or {}

    lecture_obj = LectureContent.model_validate(lecture)
    syllabus_obj = Syllabus.model_validate(syllabus)

    # Use LLM for intelligent question generation
    if use_llm:
        return _generate_with_llm(lecture_obj, syllabus_obj, config, llm_provider)

    # Fallback to template generation
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


def _generate_with_llm(
    lecture: LectureContent,
    syllabus: Syllabus,
    config: dict,
    provider_name: str,
) -> dict:
    """Generate questions using LLM.

    Args:
        lecture: Parsed lecture content
        syllabus: Parsed syllabus
        config: Question generation configuration
        provider_name: LLM provider to use

    Returns:
        QuestionSet as dict
    """
    from course_scribe.llm import get_provider

    provider = get_provider(provider_name)
    syllabus_week = syllabus.get_week(lecture.week_number)

    # Build the prompt
    prompt = _build_questions_prompt(lecture, syllabus_week, config)

    # Generate questions using LLM
    result = provider.generate_json(
        prompt=prompt,
        system_prompt=QUESTION_SYSTEM_PROMPT,
        max_tokens=8192,  # Questions can be lengthy
    )

    week_number = lecture.week_number

    # Ensure required fields exist
    if "week_number" not in result:
        result["week_number"] = week_number
    if "title" not in result:
        result["title"] = f"Week {week_number} Exam Questions"
    if "essay_questions" not in result:
        result["essay_questions"] = []
    if "calculation_questions" not in result:
        result["calculation_questions"] = []
    if "multiple_choice_questions" not in result:
        result["multiple_choice_questions"] = []

    # Add question IDs if missing
    for q in result.get("essay_questions", []):
        if "question_id" not in q:
            q["question_id"] = _generate_question_id()
        if "question_type" not in q:
            q["question_type"] = "essay"
    for q in result.get("calculation_questions", []):
        if "question_id" not in q:
            q["question_id"] = _generate_question_id()
        if "question_type" not in q:
            q["question_type"] = "calculation"
    for q in result.get("multiple_choice_questions", []):
        if "question_id" not in q:
            q["question_id"] = _generate_question_id()
        if "question_type" not in q:
            q["question_type"] = "multiple_choice"

    # Validate through Pydantic
    question_set = QuestionSet.model_validate(result)
    return question_set.model_dump()


def _build_questions_prompt(
    lecture: LectureContent,
    syllabus_week,
    config: dict,
) -> str:
    """Build the prompt for question generation."""
    essay_count = config.get("essay_count", 2)
    calc_count = config.get("calculation_count", 1)
    mc_count = config.get("mc_count", 3)
    difficulty = config.get("difficulty", "medium")

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

    # Generation requirements
    parts.append("# 問題生成要件")
    parts.append(f"- 論述問題: {essay_count}問")
    parts.append(f"- 計算問題: {calc_count}問（講義に計算内容がある場合のみ）")
    parts.append(f"- 選択問題: {mc_count}問")
    parts.append(f"- 難易度: {difficulty}")
    parts.append("")

    # Output format specification
    parts.append("# 出力形式")
    parts.append("""
以下のJSON形式で試験問題を生成してください:

{
  "week_number": <週番号>,
  "title": "<問題セットタイトル>",
  "essay_questions": [
    {
      "question_text": "<問題文>",
      "syllabus_topics": ["<関連トピック>"],
      "difficulty": "easy|medium|hard",
      "source_reference": "<出典（講義内の該当箇所）>",
      "expected_length": "<想定回答文字数>",
      "required_concepts": ["<必要な概念1>", "<必要な概念2>"],
      "model_answer": {
        "answer_text": "<模範解答>",
        "key_points": ["<採点ポイント1>", "<採点ポイント2>"],
        "grading": {
          "full_marks": <配点>,
          "criteria": ["<採点基準1>", "<採点基準2>"],
          "partial_credit_rules": ["<部分点ルール1>"],
          "common_mistakes": ["<よくある間違い1>"]
        }
      }
    }
  ],
  "calculation_questions": [
    {
      "question_text": "<問題文>",
      "syllabus_topics": ["<関連トピック>"],
      "difficulty": "easy|medium|hard",
      "source_reference": "<出典>",
      "premises": ["<前提条件1>", "<前提条件2>"],
      "variables": {
        "<変数名>": "<説明と単位>"
      },
      "calculation_steps": [
        {
          "step_number": 1,
          "description": "<手順の説明>",
          "formula": "<使用公式>",
          "calculation": "<計算過程>",
          "result": "<結果と単位>"
        }
      ],
      "final_answer": "<最終解答と単位>",
      "verification": "<検算方法>",
      "model_answer": { ... }
    }
  ],
  "multiple_choice_questions": [
    {
      "question_text": "<問題文>",
      "syllabus_topics": ["<関連トピック>"],
      "difficulty": "easy|medium|hard",
      "source_reference": "<出典>",
      "choices": [
        {"label": "a", "text": "<選択肢a>", "is_correct": true/false, "explanation": "<解説>"},
        {"label": "b", "text": "<選択肢b>", "is_correct": true/false, "explanation": "<解説>"},
        {"label": "c", "text": "<選択肢c>", "is_correct": true/false, "explanation": "<解説>"},
        {"label": "d", "text": "<選択肢d>", "is_correct": true/false, "explanation": "<解説>"}
      ],
      "correct_answer": "<正解のラベル>",
      "explanation": "<全体の解説>"
    }
  ]
}

重要:
- 問題は必ず講義内容のみに基づくこと。外部知識を前提としない。
- 計算問題は、前提条件・変数定義・計算手順・単位・検算を必ず含めること。
- 各問題には必ず模範解答と採点基準を含めること。
- シラバスのトピック・キーワードに対応する問題を生成すること。
""")

    return "\n".join(parts)
