"""Tests for summarize skill."""

import pytest
from course_scribe.skills.summarize import summarize_lecture, generate_summary_template


class TestSummarizeLecture:
    def test_generates_summary_structure(self, lecture_dict, syllabus_dict):
        result = summarize_lecture(lecture_dict, syllabus_dict)
        assert "week_number" in result
        assert "title" in result
        assert "sections" in result

    def test_includes_syllabus_alignment(self, lecture_dict, syllabus_dict):
        result = summarize_lecture(lecture_dict, syllabus_dict)
        assert "syllabus_alignment" in result
        assert isinstance(result["syllabus_alignment"], dict)

    def test_identifies_exam_focus_points(self, lecture_dict, syllabus_dict):
        result = summarize_lecture(lecture_dict, syllabus_dict)
        assert "exam_focus_points" in result

    def test_week_number_matches_lecture(self, lecture_dict, syllabus_dict):
        result = summarize_lecture(lecture_dict, syllabus_dict)
        assert result["week_number"] == lecture_dict["week_number"]


class TestGenerateSummaryTemplate:
    def test_generates_template_for_existing_week(self, syllabus_dict):
        result = generate_summary_template(syllabus_dict, week_number=1)
        assert "week_number" in result
        assert result["week_number"] == 1

    def test_returns_error_for_missing_week(self, syllabus_dict):
        result = generate_summary_template(syllabus_dict, week_number=99)
        assert "error" in result

    def test_template_has_sections_for_topics(self, syllabus_dict):
        result = generate_summary_template(syllabus_dict, week_number=1)
        if "error" not in result:
            assert len(result["sections"]) > 0


@pytest.fixture
def syllabus_dict():
    return {
        "course_name": "情報工学概論",
        "instructor": "山田太郎",
        "description": "",
        "weeks": [
            {
                "week_number": 1,
                "title": "コンピュータの基礎",
                "topics": ["コンピュータの歴史", "ハードウェアとソフトウェア"],
                "keywords": ["CPU", "メモリ"],
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
        "raw_text": "コンピュータの歴史について。CPUとメモリが重要。",
        "sections": [
            {
                "heading": "歴史",
                "content": "コンピュータの歴史について説明します。",
                "keywords_mentioned": ["CPU"],
            },
        ],
        "source_type": "txt",
        "source_filename": "lecture_01.txt",
    }
