"""Tests for validate skill."""

import copy
import re

import pytest
from course_scribe.skills.validate import (
    validate_outputs,
    validate_calculation_steps,
)
from course_scribe.schemas.validation import IssueSeverity

UNSUPPORTED_STATEMENT = (
    "Chromatin immunoprecipitation sequencing maps histone acetylation peaks "
    "at distal enhancers during zygotic genome activation in early Drosophila embryogenesis."
)

_PATH_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\[\d+\]")


def _set_path(root: dict, path: str, value: str) -> dict:
    """Set a dotted/indexed field path on a nested dict. Returns root."""
    tokens = _PATH_TOKEN_RE.findall(path)
    if not tokens:
        raise ValueError(f"unparsable path: {path}")
    current = root
    for token in tokens[:-1]:
        if token.startswith("["):
            current = current[int(token[1:-1])]
        else:
            current = current[token]
    last = tokens[-1]
    if last.startswith("["):
        current[int(last[1:-1])] = value
    else:
        current[last] = value
    return root


def _assert_scope_violation_at(result: dict, location: str) -> None:
    assert result["is_valid"] is False
    matching = [
        issue
        for issue in result["issues"]
        if issue["category"] == "scope_violation"
        and issue["severity"] == "error"
        and issue["location"] == location
    ]
    assert matching, (
        f"expected scope_violation error at {location!r}, got {result['issues']!r}"
    )


def _minimal_summary() -> dict:
    return {
        "week_number": 1,
        "title": "Summary",
        "syllabus_alignment": {"Topic A": True},
        "sections": [
            {
                "heading": "Topic A",
                "content": "Topic A",
                "syllabus_topics": ["Topic A"],
                "key_points": ["Topic A"],
            }
        ],
        "exam_focus_points": ["Topic A"],
        "uncovered_topics": [],
    }


def _model_answer(text: str = "Topic A") -> dict:
    return {
        "answer_text": text,
        "key_points": [text],
        "grading": {
            "full_marks": 10,
            "criteria": [],
            "partial_credit_rules": [],
            "common_mistakes": [],
        },
    }


def _minimal_essay_questions() -> dict:
    return {
        "week_number": 1,
        "title": "Questions",
        "essay_questions": [
            {
                "question_id": "eq1",
                "question_type": "essay",
                "question_text": "Topic A",
                "syllabus_topics": ["Topic A"],
                "difficulty": "medium",
                "source_reference": "Lecture 1",
                "expected_length": "200 words",
                "required_concepts": ["Topic A"],
                "model_answer": _model_answer(),
            }
        ],
        "calculation_questions": [],
        "multiple_choice_questions": [],
    }


def _minimal_calculation_questions() -> dict:
    return {
        "week_number": 1,
        "title": "Questions",
        "essay_questions": [],
        "calculation_questions": [
            {
                "question_id": "cq1",
                "question_type": "calculation",
                "question_text": "Topic A",
                "syllabus_topics": ["Topic A"],
                "difficulty": "medium",
                "source_reference": "Lecture 1",
                "premises": ["Topic A"],
                "variables": {"v": "Topic A"},
                "calculation_steps": [
                    {
                        "step_number": 1,
                        "description": "Topic A",
                        "formula": "Topic A",
                        "calculation": "Topic A",
                        "result": "10 m",
                    }
                ],
                "final_answer": "10 m",
                "verification": "Topic A",
                "model_answer": _model_answer(),
            }
        ],
        "multiple_choice_questions": [],
    }


def _minimal_mc_questions() -> dict:
    return {
        "week_number": 1,
        "title": "Questions",
        "essay_questions": [],
        "calculation_questions": [],
        "multiple_choice_questions": [
            {
                "question_id": "mc1",
                "question_type": "multiple_choice",
                "question_text": "Topic A",
                "syllabus_topics": ["Topic A"],
                "difficulty": "medium",
                "source_reference": "Lecture 1",
                "choices": [
                    {
                        "label": "a",
                        "text": "Topic A",
                        "is_correct": True,
                        "explanation": "Topic A",
                    },
                    {
                        "label": "b",
                        "text": "keyword1",
                        "is_correct": False,
                        "explanation": "keyword1",
                    },
                    {
                        "label": "c",
                        "text": "Topic B",
                        "is_correct": False,
                        "explanation": "Topic B",
                    },
                    {
                        "label": "d",
                        "text": "keyword1",
                        "is_correct": False,
                        "explanation": "keyword1",
                    },
                ],
                "correct_answer": "a",
                "explanation": "Topic A",
            }
        ],
    }


def _grounded_outputs(excerpt: str, lecture_text: str) -> tuple[dict, dict]:
    """Build outputs whose material fields are copied from lecture_text."""
    assert excerpt in lecture_text
    lecture = {
        "week_number": 1,
        "title": "Lecture 1",
        "raw_text": lecture_text,
        "sections": [],
        "source_type": "txt",
        "source_filename": "lecture_01.txt",
    }
    outputs = {
        "summary": {
            "week_number": 1,
            "title": excerpt,
            "syllabus_alignment": {"Topic A": True},
            "sections": [
                {
                    "heading": excerpt,
                    "content": excerpt,
                    "syllabus_topics": ["Topic A"],
                    "key_points": [excerpt],
                }
            ],
            "exam_focus_points": [excerpt],
            "uncovered_topics": [],
        },
        "questions": {
            "week_number": 1,
            "title": excerpt,
            "essay_questions": [
                {
                    "question_id": "eq1",
                    "question_type": "essay",
                    "question_text": excerpt,
                    "syllabus_topics": ["Topic A"],
                    "difficulty": "medium",
                    "source_reference": excerpt,
                    "expected_length": excerpt,
                    "required_concepts": [excerpt],
                    "model_answer": _model_answer(excerpt),
                }
            ],
            "calculation_questions": [
                {
                    "question_id": "cq1",
                    "question_type": "calculation",
                    "question_text": excerpt,
                    "syllabus_topics": ["Topic A"],
                    "difficulty": "medium",
                    "source_reference": excerpt,
                    "premises": [excerpt],
                    "variables": {"v": excerpt},
                    "calculation_steps": [
                        {
                            "step_number": 1,
                            "description": excerpt,
                            "formula": excerpt,
                            "calculation": excerpt,
                            "result": excerpt,
                        }
                    ],
                    "final_answer": excerpt,
                    "verification": excerpt,
                    "model_answer": _model_answer(excerpt),
                }
            ],
            "multiple_choice_questions": [
                {
                    "question_id": "mc1",
                    "question_type": "multiple_choice",
                    "question_text": excerpt,
                    "syllabus_topics": ["Topic A"],
                    "difficulty": "medium",
                    "source_reference": excerpt,
                    "choices": [
                        {
                            "label": "a",
                            "text": excerpt,
                            "is_correct": True,
                            "explanation": excerpt,
                        },
                        {
                            "label": "b",
                            "text": excerpt,
                            "is_correct": False,
                            "explanation": excerpt,
                        },
                        {
                            "label": "c",
                            "text": excerpt,
                            "is_correct": False,
                            "explanation": excerpt,
                        },
                        {
                            "label": "d",
                            "text": excerpt,
                            "is_correct": False,
                            "explanation": excerpt,
                        },
                    ],
                    "correct_answer": "a",
                    "explanation": excerpt,
                }
            ],
        },
    }
    return outputs, lecture


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


def test_empty_outputs_fail_closed(lecture_dict, syllabus_dict):
    result = validate_outputs({}, lecture_dict, syllabus_dict)
    assert result["is_valid"] is False
    matching = [
        issue
        for issue in result["issues"]
        if issue["category"] == "missing_content"
        and issue["severity"] == "error"
        and issue["location"] == "outputs"
    ]
    assert matching, f"expected missing_content error at 'outputs', got {result['issues']!r}"


@pytest.mark.parametrize(
    "field_path",
    [
        "summary.sections[0].content",
        "summary.sections[0].key_points[0]",
        "summary.exam_focus_points[0]",
    ],
)
def test_unsupported_summary_material_fails_closed(
    field_path, lecture_dict, syllabus_dict
):
    outputs = {"summary": copy.deepcopy(_minimal_summary())}
    _set_path(outputs, field_path, UNSUPPORTED_STATEMENT)
    result = validate_outputs(outputs, lecture_dict, syllabus_dict)
    _assert_scope_violation_at(result, field_path)


@pytest.mark.parametrize(
    "field_path",
    [
        "questions.essay_questions[0].question_text",
        "questions.essay_questions[0].required_concepts[0]",
        "questions.essay_questions[0].model_answer.answer_text",
        "questions.essay_questions[0].model_answer.key_points[0]",
    ],
)
def test_unsupported_essay_material_fails_closed(
    field_path, lecture_dict, syllabus_dict
):
    outputs = {"questions": copy.deepcopy(_minimal_essay_questions())}
    _set_path(outputs, field_path, UNSUPPORTED_STATEMENT)
    result = validate_outputs(outputs, lecture_dict, syllabus_dict)
    _assert_scope_violation_at(result, field_path)


@pytest.mark.parametrize(
    "field_path",
    [
        "questions.calculation_questions[0].question_text",
        "questions.calculation_questions[0].premises[0]",
        "questions.calculation_questions[0].variables.v",
        "questions.calculation_questions[0].calculation_steps[0].description",
        "questions.calculation_questions[0].calculation_steps[0].formula",
        "questions.calculation_questions[0].calculation_steps[0].calculation",
        "questions.calculation_questions[0].calculation_steps[0].result",
        "questions.calculation_questions[0].final_answer",
        "questions.calculation_questions[0].verification",
        "questions.calculation_questions[0].model_answer.answer_text",
        "questions.calculation_questions[0].model_answer.key_points[0]",
    ],
)
def test_unsupported_calculation_material_fails_closed(
    field_path, lecture_dict, syllabus_dict
):
    outputs = {"questions": copy.deepcopy(_minimal_calculation_questions())}
    _set_path(outputs, field_path, UNSUPPORTED_STATEMENT)
    result = validate_outputs(outputs, lecture_dict, syllabus_dict)
    _assert_scope_violation_at(result, field_path)


@pytest.mark.parametrize(
    "field_path",
    [
        "questions.multiple_choice_questions[0].question_text",
        "questions.multiple_choice_questions[0].choices[0].text",
        "questions.multiple_choice_questions[0].choices[0].explanation",
        "questions.multiple_choice_questions[0].explanation",
    ],
)
def test_unsupported_multiple_choice_material_fails_closed(
    field_path, lecture_dict, syllabus_dict
):
    outputs = {"questions": copy.deepcopy(_minimal_mc_questions())}
    _set_path(outputs, field_path, UNSUPPORTED_STATEMENT)
    result = validate_outputs(outputs, lecture_dict, syllabus_dict)
    _assert_scope_violation_at(result, field_path)


@pytest.mark.parametrize(
    "lang,lecture_text,excerpt",
    [
        (
            "en",
            (
                "Newton's second law states that the net force on a body equals "
                "mass times acceleration. Force is measured in newtons. Mass is "
                "measured in kilograms. Acceleration is measured in meters per "
                "second squared. Verification confirms that dimensional units "
                "remain consistent."
            ),
            "Force is measured in newtons.",
        ),
        (
            "ja",
            (
                "本日の講義ではニュートンの第二法則を扱う。"
                "物体に働く正味の力は質量と加速度の積に等しい。"
                "力の単位はニュートンである。質量はキログラムで表す。"
                "加速度はメートル毎秒毎秒である。"
                "検算では次元が一致することを確認する。"
            ),
            "力の単位はニュートンである。",
        ),
    ],
)
def test_grounded_english_and_japanese_material_passes(
    lang, lecture_text, excerpt, syllabus_dict
):
    outputs, lecture = _grounded_outputs(excerpt, lecture_text)
    result = validate_outputs(outputs, lecture, syllabus_dict)
    scope_errors = [
        issue
        for issue in result["issues"]
        if issue["category"] == "scope_violation" and issue["severity"] == "error"
    ]
    assert scope_errors == []
    assert result["is_valid"] is True
