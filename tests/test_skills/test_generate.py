"""Tests for generate_questions skill."""

import pytest
from course_scribe.skills.generate_questions import (
    generate_questions,
    create_question_template,
)
from course_scribe.core.types import QuestionType


class TestGenerateQuestions:
    def test_generates_question_set(self, lecture_dict, syllabus_dict):
        result = generate_questions(lecture_dict, syllabus_dict)
        assert "week_number" in result
        assert "essay_questions" in result
        assert "calculation_questions" in result
        assert "multiple_choice_questions" in result

    def test_generates_requested_essay_count(self, lecture_dict, syllabus_dict):
        config = {"essay_count": 2, "mc_count": 0, "calculation_count": 0}
        result = generate_questions(lecture_dict, syllabus_dict, config)
        assert len(result["essay_questions"]) <= 2

    def test_essay_questions_have_required_fields(self, lecture_dict, syllabus_dict):
        result = generate_questions(lecture_dict, syllabus_dict)
        for q in result["essay_questions"]:
            assert "question_id" in q
            assert "question_text" in q
            assert "syllabus_topics" in q
            assert "model_answer" in q

    def test_mc_questions_have_choices(self, lecture_dict, syllabus_dict):
        config = {"mc_count": 2, "essay_count": 0, "calculation_count": 0}
        result = generate_questions(lecture_dict, syllabus_dict, config)
        for q in result["multiple_choice_questions"]:
            assert "choices" in q
            assert len(q["choices"]) >= 2
            assert "correct_answer" in q


class TestCreateQuestionTemplate:
    def test_creates_essay_template(self):
        template = create_question_template("essay", "テスト", 1)
        assert template["question_type"] == QuestionType.ESSAY.value
        assert "question_id" in template

    def test_creates_calculation_template(self):
        template = create_question_template("calculation", "テスト", 1)
        assert template["question_type"] == QuestionType.CALCULATION.value
        assert "premises" in template
        assert "variables" in template
        assert "final_answer" in template
        assert "verification" in template

    def test_creates_mc_template(self):
        template = create_question_template("multiple_choice", "テスト", 1)
        assert template["question_type"] == QuestionType.MULTIPLE_CHOICE.value
        assert "choices" in template


class TestCalculationQuestionRequirements:
    """Verify calculation questions meet the required constraints."""

    def test_calculation_has_premises(self, lecture_with_calc, syllabus_dict):
        config = {"calculation_count": 1, "essay_count": 0, "mc_count": 0}
        result = generate_questions(lecture_with_calc, syllabus_dict, config)
        for q in result["calculation_questions"]:
            assert "premises" in q
            assert len(q["premises"]) > 0

    def test_calculation_has_variables(self, lecture_with_calc, syllabus_dict):
        config = {"calculation_count": 1, "essay_count": 0, "mc_count": 0}
        result = generate_questions(lecture_with_calc, syllabus_dict, config)
        for q in result["calculation_questions"]:
            assert "variables" in q

    def test_calculation_has_steps(self, lecture_with_calc, syllabus_dict):
        config = {"calculation_count": 1, "essay_count": 0, "mc_count": 0}
        result = generate_questions(lecture_with_calc, syllabus_dict, config)
        for q in result["calculation_questions"]:
            assert "calculation_steps" in q

    def test_calculation_has_verification(self, lecture_with_calc, syllabus_dict):
        config = {"calculation_count": 1, "essay_count": 0, "mc_count": 0}
        result = generate_questions(lecture_with_calc, syllabus_dict, config)
        for q in result["calculation_questions"]:
            assert "verification" in q


@pytest.fixture
def syllabus_dict():
    return {
        "course_name": "情報工学概論",
        "instructor": "",
        "description": "",
        "weeks": [
            {
                "week_number": 1,
                "title": "コンピュータの基礎",
                "topics": ["二進数変換", "計算"],
                "keywords": ["ビット", "バイト", "二進数"],
                "learning_objectives": [],
            },
        ],
        "total_weeks": 1,
    }


@pytest.fixture
def lecture_dict():
    return {
        "week_number": 1,
        "title": "コンピュータの基礎",
        "raw_text": "二進数とビットについて学びます。",
        "sections": [
            {
                "heading": "二進数",
                "content": "二進数の説明",
                "keywords_mentioned": ["二進数"],
            },
        ],
        "source_type": "txt",
        "source_filename": "lecture_01.txt",
    }


@pytest.fixture
def lecture_with_calc():
    return {
        "week_number": 1,
        "title": "コンピュータの基礎",
        "raw_text": "二進数の計算をします。5 = 101 (二進数)。公式: n = Σ(bi * 2^i)",
        "sections": [
            {
                "heading": "計算",
                "content": "計算の方法を説明。結果 = 5",
                "keywords_mentioned": ["計算"],
            },
        ],
        "source_type": "txt",
        "source_filename": "lecture_01.txt",
    }
