"""Tests for ingest skill."""

import pytest
from course_scribe.skills.ingest import ingest_document, _extract_week_number


class TestExtractWeekNumber:
    def test_extracts_from_lecture_filename(self):
        assert _extract_week_number("lecture_01.txt") == 1
        assert _extract_week_number("lecture_12.md") == 12

    def test_extracts_from_transcript_filename(self):
        assert _extract_week_number("transcript_03.txt") == 3

    def test_returns_none_for_no_number(self):
        assert _extract_week_number("syllabus.txt") is None


class TestIngestSyllabus:
    def test_parses_course_name(self, sample_syllabus_content):
        result = ingest_document(
            content=sample_syllabus_content,
            document_type="txt",
            source_filename="syllabus.txt",
            is_syllabus=True,
        )
        assert result["course_name"] == "情報工学概論"

    def test_parses_instructor(self, sample_syllabus_content):
        result = ingest_document(
            content=sample_syllabus_content,
            document_type="txt",
            source_filename="syllabus.txt",
            is_syllabus=True,
        )
        assert "山田" in result["instructor"]

    def test_parses_weeks(self, sample_syllabus_content):
        result = ingest_document(
            content=sample_syllabus_content,
            document_type="txt",
            source_filename="syllabus.txt",
            is_syllabus=True,
        )
        assert result["total_weeks"] >= 3
        assert len(result["weeks"]) >= 3

    def test_week_has_topics(self, sample_syllabus_content):
        result = ingest_document(
            content=sample_syllabus_content,
            document_type="txt",
            source_filename="syllabus.txt",
            is_syllabus=True,
        )
        week1 = result["weeks"][0]
        assert len(week1["topics"]) > 0

    def test_week_has_keywords(self, sample_syllabus_content):
        result = ingest_document(
            content=sample_syllabus_content,
            document_type="txt",
            source_filename="syllabus.txt",
            is_syllabus=True,
        )
        week1 = result["weeks"][0]
        assert "CPU" in week1["keywords"] or "メモリ" in week1["keywords"]


class TestIngestLecture:
    def test_parses_lecture_content(self, sample_lecture_content):
        result = ingest_document(
            content=sample_lecture_content,
            document_type="txt",
            source_filename="lecture_01.txt",
            week_number=1,
            is_syllabus=False,
        )
        assert result["week_number"] == 1
        assert result["source_type"] == "txt"

    def test_extracts_sections(self, sample_lecture_content):
        result = ingest_document(
            content=sample_lecture_content,
            document_type="txt",
            source_filename="lecture_01.txt",
            week_number=1,
            is_syllabus=False,
        )
        assert len(result["sections"]) > 0

    def test_extracts_keywords_from_bold(self, sample_lecture_content):
        result = ingest_document(
            content=sample_lecture_content,
            document_type="txt",
            source_filename="lecture_01.txt",
            week_number=1,
            is_syllabus=False,
        )
        # Should extract bold terms like **CPU**, **メモリ**
        all_keywords = set()
        for section in result["sections"]:
            all_keywords.update(section["keywords_mentioned"])
        assert len(all_keywords) > 0

    def test_auto_detects_week_from_filename(self, sample_lecture_content):
        result = ingest_document(
            content=sample_lecture_content,
            document_type="txt",
            source_filename="lecture_03.txt",
            is_syllabus=False,
        )
        assert result["week_number"] == 3


# Fixtures
@pytest.fixture
def sample_syllabus_content():
    return """# 情報工学概論
担当: 山田太郎

## Week 1: コンピュータの基礎
トピック:
- コンピュータの歴史
- ハードウェアとソフトウェア
- 二進数と情報表現

キーワード:
- CPU
- メモリ
- ビット

## Week 2: プログラミング入門
トピック:
- プログラミング言語の種類
- アルゴリズムとは

キーワード:
- アルゴリズム
- 変数

## Week 3: データ構造
トピック:
- 配列とリスト
- スタックとキュー

キーワード:
- 配列
- スタック
"""


@pytest.fixture
def sample_lecture_content():
    return """# 第1回講義: コンピュータの基礎

## コンピュータの歴史

コンピュータの歴史は、**ENIAC**から始まります。

## ハードウェアとソフトウェア

コンピュータは**ハードウェア**と**ソフトウェア**から構成されます。
- **CPU**: 計算を行う頭脳
- **メモリ**: データを保存

## 二進数と情報表現

**ビット**は情報の最小単位です。
**バイト**は8ビットです。
"""
