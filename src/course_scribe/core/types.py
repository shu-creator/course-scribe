"""Core type definitions."""

from enum import Enum


class DocumentType(str, Enum):
    """Supported document types for ingestion."""

    PDF = "pdf"
    MARKDOWN = "md"
    TEXT = "txt"


class QuestionType(str, Enum):
    """Types of exam questions."""

    ESSAY = "essay"  # 論述問題
    CALCULATION = "calculation"  # 計算問題
    MULTIPLE_CHOICE = "multiple_choice"  # 選択問題
