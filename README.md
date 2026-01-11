# course-scribe

Syllabus-aligned lecture summarization and exam question generator from transcripts and course materials.

## Overview

course-scribe generates:
1. **Structured summaries** aligned with syllabus topics
2. **Exam questions** (essay, calculation, multiple choice)
3. **Model answers** with grading criteria

All outputs are strictly validated to stay within syllabus and lecture scope.

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Ingest    │───▶│   Align     │───▶│  Summarize  │
│  (PDF/MD)   │    │  Syllabus   │    │             │
└─────────────┘    └─────────────┘    └──────┬──────┘
                                             │
                                             ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Export    │◀───│  Validate   │◀───│  Generate   │
│             │    │             │    │  Questions  │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Skills (Reusable Pure Functions)

Each skill is a pure function with JSON input/output:

| Skill | Input | Output | Purpose |
|-------|-------|--------|---------|
| `ingest_document` | Raw text + metadata | Syllabus/LectureContent | Parse documents |
| `align_with_syllabus` | Lecture + Syllabus | Alignment result | Check scope compliance |
| `summarize_lecture` | Lecture + Syllabus | StructuredSummary | Generate summaries |
| `generate_questions` | Lecture + Syllabus | QuestionSet | Create exam questions |
| `validate_outputs` | Outputs + Sources | ValidationResult | Quality assurance |

## Installation

```bash
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

## Usage

### CLI Commands

```bash
# Full pipeline
course-scribe process syllabus.txt lecture_01.txt -o output/

# Individual steps
course-scribe ingest-syllabus syllabus.txt -o syllabus.json
course-scribe ingest-lecture lecture_01.txt -w 1 -o lecture.json
course-scribe align lecture.json syllabus.json
course-scribe summarize lecture.json syllabus.json -o summary.md
course-scribe questions lecture.json syllabus.json -o questions.json
course-scribe validate lecture.json syllabus.json --summary summary.json --questions questions.json
```

### Python API

```python
from course_scribe.skills import (
    ingest_document,
    align_with_syllabus,
    summarize_lecture,
    generate_questions,
    validate_outputs,
)

# Ingest syllabus
syllabus = ingest_document(
    content=syllabus_text,
    document_type="txt",
    is_syllabus=True,
)

# Ingest lecture
lecture = ingest_document(
    content=lecture_text,
    document_type="txt",
    week_number=1,
)

# Check alignment
alignment = align_with_syllabus(lecture, syllabus)

# Generate summary
summary = summarize_lecture(lecture, syllabus, alignment)

# Generate questions
questions = generate_questions(lecture, syllabus)

# Validate outputs
validation = validate_outputs(
    {"summary": summary, "questions": questions},
    lecture,
    syllabus,
)
```

## Output Formats

### Summary (Markdown)
```markdown
# Week 1 Summary
**Week 1**

## Exam Focus Points
- Understand: CPU
- Contains formulas - review calculation steps

## Section Heading
Content...

**Key Points:**
- Key point 1
- Key point 2
```

### Questions (JSON)
```json
{
  "week_number": 1,
  "essay_questions": [...],
  "calculation_questions": [...],
  "multiple_choice_questions": [...]
}
```

## Design Principles

1. **Skill-first**: Each module is a pure function, ready for extraction as a standalone skill
2. **Schema-bound**: All I/O uses Pydantic models with JSON Schema export
3. **Boundary separation**: File I/O only at CLI layer, core logic is pure
4. **Scope enforcement**: Validation prevents content outside syllabus/lecture scope

## Constraints

- All summaries/questions must be based on lecture content only
- No external knowledge or interpolation allowed
- Calculation questions require: premises, variables, steps, units, verification
- Scope violations are flagged during validation

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=course_scribe
```

## License

MIT
