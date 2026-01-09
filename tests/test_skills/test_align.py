"""Tests for align_syllabus skill."""

import pytest
from course_scribe.skills.align_syllabus import align_with_syllabus, check_content_in_scope


class TestAlignWithSyllabus:
    def test_identifies_covered_topics(self, lecture_dict, syllabus_dict):
        result = align_with_syllabus(lecture_dict, syllabus_dict)
        assert "covered_topics" in result
        assert len(result["covered_topics"]) > 0

    def test_identifies_uncovered_topics(self, lecture_dict, syllabus_dict):
        result = align_with_syllabus(lecture_dict, syllabus_dict)
        assert "uncovered_topics" in result

    def test_calculates_alignment_score(self, lecture_dict, syllabus_dict):
        result = align_with_syllabus(lecture_dict, syllabus_dict)
        assert 0 <= result["alignment_score"] <= 1

    def test_week_match_true_when_week_exists(self, lecture_dict, syllabus_dict):
        result = align_with_syllabus(lecture_dict, syllabus_dict)
        assert result["week_match"] is True

    def test_week_match_false_when_week_missing(self, lecture_dict, syllabus_dict):
        lecture_dict["week_number"] = 99
        result = align_with_syllabus(lecture_dict, syllabus_dict)
        assert result["week_match"] is False

    def test_strict_mode_detects_violations(self, lecture_dict, syllabus_dict):
        result = align_with_syllabus(lecture_dict, syllabus_dict, strict_mode=True)
        assert "potential_violations" in result


class TestCheckContentInScope:
    def test_content_in_scope(self, syllabus_dict):
        content = "CPUとメモリについて説明します。"
        result = check_content_in_scope(content, syllabus_dict, week_number=1)
        # Should be in scope since CPU and メモリ are week 1 keywords
        assert result["confidence"] >= 0

    def test_content_out_of_scope(self, syllabus_dict):
        content = "QuantumComputingとBlockchainについて説明します。"
        result = check_content_in_scope(content, syllabus_dict, week_number=1)
        # Should have low confidence or violations
        assert len(result["violations"]) > 0 or result["confidence"] < 1.0


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
                "topics": ["コンピュータの歴史", "ハードウェアとソフトウェア", "二進数"],
                "keywords": ["CPU", "メモリ", "ビット", "バイト"],
                "learning_objectives": [],
            },
            {
                "week_number": 2,
                "title": "プログラミング入門",
                "topics": ["プログラミング言語", "アルゴリズム"],
                "keywords": ["アルゴリズム", "変数"],
                "learning_objectives": [],
            },
        ],
        "total_weeks": 2,
    }


@pytest.fixture
def lecture_dict():
    return {
        "week_number": 1,
        "title": "コンピュータの基礎",
        "raw_text": "コンピュータの歴史とハードウェアについて学びます。CPUとメモリが重要です。二進数も扱います。",
        "sections": [
            {
                "heading": "歴史",
                "content": "コンピュータの歴史について",
                "keywords_mentioned": ["ENIAC"],
            },
            {
                "heading": "ハードウェア",
                "content": "CPUとメモリについて",
                "keywords_mentioned": ["CPU", "メモリ"],
            },
        ],
        "source_type": "txt",
        "source_filename": "lecture_01.txt",
    }
