"""Tests for validate skill."""

import pytest
from course_scribe.skills.validate import (
    validate_outputs,
    validate_calculation_steps,
)
from course_scribe.schemas.validation import IssueSeverity


class TestValidateOutputs:
    def test_returns_validation_result(self, lecture_dict, syllabus_dict, summary_dict):
        outputs = {"summary": summary_dict}
        result = validate_outputs(outputs, lecture_dict, syllabus_dict)
        assert "is_valid" in result
        assert "issues" in result
        assert "checked_items" in result

    def test_validates_summary(self, lecture_dict, syllabus_dict, summary_dict):
        outputs = {"summary": summary_dict}
        result = validate_outputs(outputs, lecture_dict, syllabus_dict)
        assert "Summary structure" in " ".join(result["checked_items"])

    def test_validates_questions(self, lecture_dict, syllabus_dict, questions_dict):
        outputs = {"questions": questions_dict}
        result = validate_outputs(outputs, lecture_dict, syllabus_dict)
        assert "Question scope" in " ".join(result["checked_items"])

    def test_detects_week_mismatch(self, lecture_dict, syllabus_dict, summary_dict):
        summary_dict["week_number"] = 99
        outputs = {"summary": summary_dict}
        result = validate_outputs(outputs, lecture_dict, syllabus_dict)
        assert not result["is_valid"]
        assert any("week" in i["message"].lower() for i in result["issues"])


class TestValidateCalculationSteps:
    def test_valid_steps_pass(self):
        steps = [
            {
                "step_number": 1,
                "description": "First step",
                "calculation": "5 * 2",
                "result": "10 m",
            },
        ]
        result = validate_calculation_steps(steps)
        assert result["is_valid"]

    def test_missing_description_fails(self):
        steps = [
            {
                "step_number": 1,
                "calculation": "5 * 2",
                "result": "10",
            },
        ]
        result = validate_calculation_steps(steps)
        assert not result["is_valid"]
        assert any("description" in e.lower() for e in result["errors"])

    def test_missing_result_fails(self):
        steps = [
            {
                "step_number": 1,
                "description": "First step",
                "calculation": "5 * 2",
            },
        ]
        result = validate_calculation_steps(steps)
        assert not result["is_valid"]

    def test_warns_missing_units(self):
        steps = [
            {
                "step_number": 1,
                "description": "First step",
                "calculation": "5 * 2",
                "result": "10",  # No units
            },
        ]
        result = validate_calculation_steps(steps)
        assert any("unit" in e.lower() for e in result["errors"])


class TestMCQuestionValidation:
    def test_detects_multiple_correct_answers(self, lecture_dict, syllabus_dict):
        questions = {
            "week_number": 1,
            "title": "Test",
            "essay_questions": [],
            "calculation_questions": [],
            "multiple_choice_questions": [
                {
                    "question_id": "q1",
                    "question_type": "multiple_choice",
                    "question_text": "Test?",
                    "syllabus_topics": [],
                    "difficulty": "medium",
                    "source_reference": "",
                    "choices": [
                        {"label": "a", "text": "A", "is_correct": True, "explanation": ""},
                        {"label": "b", "text": "B", "is_correct": True, "explanation": ""},  # Two correct!
                    ],
                    "correct_answer": "a",
                    "explanation": "",
                }
            ],
        }
        result = validate_outputs({"questions": questions}, lecture_dict, syllabus_dict)
        assert any("correct" in i["message"].lower() for i in result["issues"])


@pytest.fixture
def syllabus_dict():
    return {
        "course_name": "Test Course",
        "instructor": "",
        "description": "",
        "weeks": [
            {
                "week_number": 1,
                "title": "Week 1",
                "topics": ["Topic A", "Topic B"],
                "keywords": ["keyword1"],
                "learning_objectives": [],
            },
        ],
        "total_weeks": 1,
    }


@pytest.fixture
def lecture_dict():
    return {
        "week_number": 1,
        "title": "Lecture 1",
        "raw_text": "Content about Topic A and keyword1",
        "sections": [],
        "source_type": "txt",
        "source_filename": "lecture_01.txt",
    }


@pytest.fixture
def summary_dict():
    return {
        "week_number": 1,
        "title": "Summary",
        "syllabus_alignment": {"Topic A": True},
        "sections": [
            {
                "heading": "Test",
                "content": "Test content",
                "syllabus_topics": ["Topic A"],
                "key_points": [],
            }
        ],
        "exam_focus_points": [],
        "uncovered_topics": [],
    }


@pytest.fixture
def questions_dict():
    return {
        "week_number": 1,
        "title": "Questions",
        "essay_questions": [
            {
                "question_id": "q1",
                "question_type": "essay",
                "question_text": "Explain Topic A",
                "syllabus_topics": ["Topic A"],
                "difficulty": "medium",
                "source_reference": "Lecture 1",
                "expected_length": "200 words",
                "required_concepts": [],
                "model_answer": {
                    "answer_text": "Answer",
                    "key_points": [],
                    "grading": {
                        "full_marks": 10,
                        "criteria": [],
                        "partial_credit_rules": [],
                        "common_mistakes": [],
                    },
                },
            }
        ],
        "calculation_questions": [],
        "multiple_choice_questions": [],
    }
