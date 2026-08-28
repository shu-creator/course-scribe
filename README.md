# course-scribe

シラバスに沿った講義要約と試験問題を自動生成するツール

## 概要

course-scribeは以下を生成します：
1. **構造化要約** - シラバスのトピックに沿った講義要約
2. **試験問題** - 論述・計算・選択問題
3. **模範解答** - 採点基準・部分点ルール付き

すべての出力はシラバスと講義内容の範囲内に制限されます。

## 対応フォーマット

| フォーマット | 対応 | 備考 |
|-------------|------|------|
| Markdown (.md) | ✅ | |
| Text (.txt) | ✅ | |
| PDF (.pdf) | ✅ | OCR対応 |
| Word (.docx) | ✅ | |
| PowerPoint (.pptx) | ✅ | |

## インストール

```bash
# 基本インストール
pip install -e .

# 開発用
pip install -e ".[dev]"

# OCR対応（スキャンPDF用）
pip install -e ".[ocr]"
# + Tesseract OCRのインストールが必要
#   macOS: brew install tesseract tesseract-lang
#   Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-jpn
```

## 使い方

### 方法1: Claude Codeスラッシュコマンド（推奨）

Claude Code内で以下のコマンドを実行：

```
/exam-prep シラバス.pdf 講義.pptx 1
```

Claude Codeが自動的に：
1. ファイルを解析
2. 要約を生成
3. 試験問題を作成

### 方法2: Python API

```python
from course_scribe.skills import (
    ingest_document,
    summarize_lecture,
    generate_questions,
)

# シラバス読み込み
syllabus = ingest_document(
    content=syllabus_text,
    document_type="md",
    is_syllabus=True,
)

# 講義読み込み
lecture = ingest_document(
    content=lecture_text,
    document_type="md",
    week_number=1,
)

# 要約生成（LLM使用）
summary = summarize_lecture(lecture, syllabus, use_llm=True)

# 問題生成（LLM使用）
questions = generate_questions(lecture, syllabus, use_llm=True)
```

### 方法3: CLIコマンド

```bash
# フルパイプライン
course-scribe process syllabus.txt lecture_01.txt -o output/

# 個別ステップ
course-scribe ingest-syllabus syllabus.txt -o syllabus.json
course-scribe ingest-lecture lecture_01.txt -w 1 -o lecture.json
course-scribe summarize lecture.json syllabus.json -o summary.md
course-scribe questions lecture.json syllabus.json -o questions.json
```

## アーキテクチャ

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Ingest    │───▶│   Align     │───▶│  Summarize  │
│ (PDF/Word/  │    │  Syllabus   │    │   (LLM)     │
│  PowerPoint)│    └─────────────┘    └──────┬──────┘
└─────────────┘                              │
                                             ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Export    │◀───│  Validate   │◀───│  Generate   │
│             │    │             │    │  Questions  │
└─────────────┘    └─────────────┘    │   (LLM)     │
                                      └─────────────┘
```

### スキル一覧

| スキル | 入力 | 出力 | 用途 |
|--------|------|------|------|
| `ingest_document` | テキスト + メタデータ | Syllabus/Lecture | ドキュメント解析 |
| `align_with_syllabus` | Lecture + Syllabus | Alignment | スコープ確認 |
| `summarize_lecture` | Lecture + Syllabus | Summary | 要約生成 |
| `generate_questions` | Lecture + Syllabus | QuestionSet | 問題生成 |
| `validate_outputs` | Outputs + Sources | Validation | 品質検証 |

## 出力形式

### 要約
```markdown
# Week 1 試験対策資料

## 講義要約
[構造化された要約]

## 試験重要ポイント
- ポイント1
- ポイント2
```

### 問題
```json
{
  "week_number": 1,
  "essay_questions": [...],
  "calculation_questions": [...],
  "multiple_choice_questions": [...]
}
```

## 制約事項

- すべての要約・問題は講義内容のみに基づく
- 外部知識や推測は禁止
- 計算問題には必須: 前提条件、変数定義、計算手順、単位、検算

`validate_outputs` はこの契約を検査する。講義本文から明らかに支持されない内容は fail-closed とし、曖昧な語彙重複は確定的な hallucination 判定にしない。

| 判定 | 条件 | 結果 |
|------|------|------|
| fail-closed | 要約・論述・計算・選択の対象フィールドに、講義本文から明らかに支持されない長い技術的記述が含まれる。講義由来トークンが1語だけ重なる場合も、未支持の残りをマスクしない | `category=scope_violation`, `severity=error`, `is_valid=false`。`location` は対象フィールドの安定したドット／インデックスパス（例: `summary.sections[0].content`） |
| Japanese paraphrase (non-error) | 講義に根拠のある40文字以上の日本語言い換えで、本文の完全な部分文字列ではない | スコープ error にしない（`is_valid=true`、scope error 0） |
| heuristic (warning) | 2語以上の語彙部分一致など、根拠が不確実な overlap | 既存の warning に留める。error には昇格しない |
| empty outputs | 要約も問題もない | `category=missing_content`, `severity=error`, `location=outputs`, `is_valid=false` |

## 開発

```bash
# テスト実行
python -m pytest

# カバレッジ付き
python -m pytest --cov=course_scribe
```

## ライセンス

MIT
