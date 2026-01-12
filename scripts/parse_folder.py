#!/usr/bin/env python3
"""Parse syllabus and multiple lecture files from a folder.

Usage:
    python scripts/parse_folder.py <syllabus_file> <lectures_folder>

Output:
    JSON with parsed syllabus and all lecture files with detected week numbers
"""

import json
import re
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from course_scribe.core.readers import read_file, FileReadError

# Supported file extensions
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md"}


def extract_week_number(filename: str) -> int | None:
    """Extract week number from filename.

    Supports patterns like:
    - 第1回, 第01回, 第１回
    - Week1, Week 1, week01
    - 01_, 1_, 01-
    - lecture_01, lecture1
    """
    name = filename.lower()

    # Pattern: 第N回 (Japanese)
    match = re.search(r'第[　\s]*([0-9０-９]+)[　\s]*回', filename)
    if match:
        num_str = match.group(1)
        # Convert full-width numbers to half-width
        num_str = num_str.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        return int(num_str)

    # Pattern: Week N or WeekN
    match = re.search(r'week[_\s-]*(\d+)', name)
    if match:
        return int(match.group(1))

    # Pattern: lecture_N or lectureN
    match = re.search(r'lecture[_\s-]*(\d+)', name)
    if match:
        return int(match.group(1))

    # Pattern: Leading number (01_, 1-, etc.)
    match = re.match(r'^(\d+)[_\-\s]', name)
    if match:
        return int(match.group(1))

    # Pattern: Number in filename
    match = re.search(r'(\d+)', name)
    if match:
        return int(match.group(1))

    return None


def scan_folder(folder_path: Path) -> list[dict]:
    """Scan folder for supported files and extract week numbers."""
    files = []

    for ext in SUPPORTED_EXTENSIONS:
        for file_path in folder_path.glob(f"*{ext}"):
            if file_path.is_file():
                week_num = extract_week_number(file_path.stem)
                files.append({
                    "path": str(file_path),
                    "filename": file_path.name,
                    "week_number": week_num,
                    "extension": ext
                })

    # Sort by week number (None values at the end)
    files.sort(key=lambda x: (x["week_number"] is None, x["week_number"] or 0))

    return files


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/parse_folder.py <syllabus_file> <lectures_folder>")
        sys.exit(1)

    syllabus_path = Path(sys.argv[1])
    lectures_folder = Path(sys.argv[2])

    result = {
        "success": True,
        "syllabus": None,
        "lectures": [],
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

    # Scan and read lectures
    if not lectures_folder.is_dir():
        result["errors"].append(f"講義フォルダが見つかりません: {lectures_folder}")
    else:
        lecture_files = scan_folder(lectures_folder)

        if not lecture_files:
            result["errors"].append(f"講義ファイルが見つかりません（対応形式: {', '.join(SUPPORTED_EXTENSIONS)}）")

        for file_info in lecture_files:
            try:
                content = read_file(Path(file_info["path"]))
                result["lectures"].append({
                    "filename": file_info["filename"],
                    "week_number": file_info["week_number"],
                    "content": content
                })
            except FileReadError as e:
                result["errors"].append(f"講義資料読み込みエラー ({file_info['filename']}): {e}")
            except Exception as e:
                result["errors"].append(f"エラー ({file_info['filename']}): {e}")

    if result["errors"]:
        result["success"] = False

    # Summary
    result["summary"] = {
        "total_lectures": len(result["lectures"]),
        "weeks_detected": [l["week_number"] for l in result["lectures"] if l["week_number"]],
        "weeks_unknown": [l["filename"] for l in result["lectures"] if not l["week_number"]]
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
