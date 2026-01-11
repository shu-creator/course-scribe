#!/usr/bin/env python3
"""Parse syllabus and lecture files for exam preparation.

Usage:
    python scripts/parse_files.py <syllabus_file> <lecture_file> [week_number]

Output:
    JSON with parsed syllabus and lecture content
"""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from course_scribe.core.readers import read_file, FileReadError


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/parse_files.py <syllabus_file> <lecture_file> [week_number]")
        sys.exit(1)

    syllabus_path = Path(sys.argv[1])
    lecture_path = Path(sys.argv[2])
    week_number = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    result = {
        "success": True,
        "week_number": week_number,
        "syllabus": None,
        "lecture": None,
        "errors": []
    }

    # Read syllabus
    try:
        result["syllabus"] = {
            "filename": syllabus_path.name,
            "content": read_file(syllabus_path)
        }
    except FileReadError as e:
        result["errors"].append(f"シラバス読み込みエラー: {e}")
    except FileNotFoundError:
        result["errors"].append(f"シラバスファイルが見つかりません: {syllabus_path}")

    # Read lecture
    try:
        result["lecture"] = {
            "filename": lecture_path.name,
            "content": read_file(lecture_path)
        }
    except FileReadError as e:
        result["errors"].append(f"講義資料読み込みエラー: {e}")
    except FileNotFoundError:
        result["errors"].append(f"講義ファイルが見つかりません: {lecture_path}")

    if result["errors"]:
        result["success"] = False

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
