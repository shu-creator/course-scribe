#!/usr/bin/env python3
"""Parse syllabus and multiple lecture files from a folder.

Usage:
    # List files only (for week assignment)
    python scripts/parse_folder.py <syllabus_file> <lectures_folder> --list-only

    # Parse with week mapping
    python scripts/parse_folder.py <syllabus_file> <lectures_folder> --week-map '{"file1.pdf": 1, "file2.pdf": 2}'

    # Parse single week
    python scripts/parse_folder.py <syllabus_file> <lectures_folder> --week 1 --files "file1.pdf,file2.txt"

Output:
    JSON with parsed syllabus and lecture files
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from course_scribe.core.readers import read_file, FileReadError

# Supported file extensions
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md"}

# File type categories
LECTURE_EXTENSIONS = {".pdf", ".docx", ".pptx"}
TRANSCRIPT_EXTENSIONS = {".txt", ".md"}


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

    return None


def extract_date_pattern(filename: str) -> str | None:
    """Extract date pattern from filename for matching related files.

    Supports patterns like:
    - 0412, 04-12, 04_12 (MMDD)
    - 20240412 (YYYYMMDD)
    - 2024-04-12, 2024_04_12
    """
    # Pattern: YYYYMMDD or YYYY-MM-DD or YYYY_MM_DD
    match = re.search(r'(20\d{2})[-_]?(\d{2})[-_]?(\d{2})', filename)
    if match:
        return f"{match.group(1)}{match.group(2)}{match.group(3)}"

    # Pattern: MMDD (4 digits that look like a date)
    match = re.search(r'(?<!\d)(0[1-9]|1[0-2])[-_]?(0[1-9]|[12]\d|3[01])(?!\d)', filename)
    if match:
        return f"{match.group(1)}{match.group(2)}"

    return None


def get_file_type(extension: str) -> str:
    """Categorize file by extension."""
    if extension.lower() in LECTURE_EXTENSIONS:
        return "lecture"
    elif extension.lower() in TRANSCRIPT_EXTENSIONS:
        return "transcript"
    return "other"


def scan_folder(folder_path: Path) -> list[dict]:
    """Scan folder for supported files and extract week numbers."""
    files = []

    for ext in SUPPORTED_EXTENSIONS:
        for file_path in folder_path.glob(f"*{ext}"):
            if file_path.is_file():
                week_num = extract_week_number(file_path.stem)
                date_pattern = extract_date_pattern(file_path.stem)
                file_type = get_file_type(ext)
                # Get file modification time for sorting
                mtime = os.path.getmtime(file_path)
                files.append({
                    "path": str(file_path),
                    "filename": file_path.name,
                    "week_number": week_num,
                    "extension": ext,
                    "mtime": mtime,
                    "file_type": file_type,
                    "date_pattern": date_pattern
                })

    # Sort by modification time (oldest first) for sequential assignment
    files.sort(key=lambda x: x["mtime"])

    return files


def group_files_by_week(files: list[dict]) -> dict:
    """Group files by week, auto-matching lectures with transcripts.

    Matching strategies:
    1. Same week number detected in filename
    2. Same date pattern in filename
    3. Modification time proximity (within 24 hours)
    """
    from datetime import datetime, timedelta

    groups = {}  # week_number -> {"lectures": [], "transcripts": []}
    unmatched_transcripts = []

    # First pass: group files with detected week numbers
    for f in files:
        if f["week_number"] is not None:
            week = f["week_number"]
            if week not in groups:
                groups[week] = {"lectures": [], "transcripts": [], "files": []}
            if f["file_type"] == "lecture":
                groups[week]["lectures"].append(f)
            elif f["file_type"] == "transcript":
                groups[week]["transcripts"].append(f)
            groups[week]["files"].append(f)
        elif f["file_type"] == "transcript":
            unmatched_transcripts.append(f)

    # Second pass: match transcripts by date pattern
    for transcript in unmatched_transcripts[:]:
        if transcript["date_pattern"]:
            matched = False
            for week, group in groups.items():
                for lecture in group["lectures"]:
                    if lecture["date_pattern"] == transcript["date_pattern"]:
                        group["transcripts"].append(transcript)
                        group["files"].append(transcript)
                        unmatched_transcripts.remove(transcript)
                        matched = True
                        break
                if matched:
                    break

    # Third pass: match transcripts by modification time proximity (within 24 hours)
    TIME_THRESHOLD = 24 * 60 * 60  # 24 hours in seconds

    for transcript in unmatched_transcripts[:]:
        best_match = None
        best_diff = float('inf')

        for week, group in groups.items():
            for lecture in group["lectures"]:
                time_diff = abs(transcript["mtime"] - lecture["mtime"])
                if time_diff < TIME_THRESHOLD and time_diff < best_diff:
                    best_diff = time_diff
                    best_match = week

        if best_match is not None:
            groups[best_match]["transcripts"].append(transcript)
            groups[best_match]["files"].append(transcript)
            unmatched_transcripts.remove(transcript)

    return groups, unmatched_transcripts


def list_files_only(syllabus_path: Path, lectures_folder: Path) -> dict:
    """List files without reading content."""
    result = {
        "success": True,
        "mode": "list",
        "syllabus": {"filename": syllabus_path.name, "exists": syllabus_path.exists()},
        "files": [],
        "grouped_by_week": {},
        "unmatched_transcripts": [],
        "errors": []
    }

    if not lectures_folder.is_dir():
        result["errors"].append(f"講義フォルダが見つかりません: {lectures_folder}")
        result["success"] = False
        return result

    files = scan_folder(lectures_folder)

    for idx, f in enumerate(files, 1):
        result["files"].append({
            "index": idx,
            "filename": f["filename"],
            "detected_week": f["week_number"],
            "extension": f["extension"],
            "file_type": f["file_type"],
            "date_pattern": f["date_pattern"]
        })

    if not files:
        result["errors"].append(f"講義ファイルが見つかりません（対応形式: {', '.join(SUPPORTED_EXTENSIONS)}）")
        return result

    # Group files by week
    groups, unmatched = group_files_by_week(files)

    # Convert groups to serializable format
    for week, group in sorted(groups.items()):
        result["grouped_by_week"][week] = {
            "lectures": [f["filename"] for f in group["lectures"]],
            "transcripts": [f["filename"] for f in group["transcripts"]],
            "all_files": [f["filename"] for f in group["files"]]
        }

    result["unmatched_transcripts"] = [f["filename"] for f in unmatched]

    # Summary
    result["summary"] = {
        "total_files": len(files),
        "lectures": len([f for f in files if f["file_type"] == "lecture"]),
        "transcripts": len([f for f in files if f["file_type"] == "transcript"]),
        "weeks_detected": list(groups.keys()),
        "unmatched_count": len(unmatched)
    }

    return result


def parse_single_week(syllabus_path: Path, lectures_folder: Path, week: int, filenames: list[str]) -> dict:
    """Parse syllabus and specific files for a single week."""
    result = {
        "success": True,
        "mode": "single_week",
        "week_number": week,
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

    # Read specified files
    for filename in filenames:
        file_path = lectures_folder / filename
        try:
            content = read_file(file_path)
            result["lectures"].append({
                "filename": filename,
                "week_number": week,
                "content": content
            })
        except FileReadError as e:
            result["errors"].append(f"講義資料読み込みエラー ({filename}): {e}")
        except FileNotFoundError:
            result["errors"].append(f"ファイルが見つかりません: {filename}")
        except Exception as e:
            result["errors"].append(f"エラー ({filename}): {e}")

    if result["errors"]:
        result["success"] = False

    return result


def parse_with_week_map(syllabus_path: Path, lectures_folder: Path, week_map: dict) -> dict:
    """Parse files with explicit week mapping."""
    result = {
        "success": True,
        "mode": "week_map",
        "syllabus": None,
        "lectures": [],
        "weeks": {},
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

    # Group files by week
    for filename, week in week_map.items():
        file_path = lectures_folder / filename
        try:
            content = read_file(file_path)
            result["lectures"].append({
                "filename": filename,
                "week_number": week,
                "content": content
            })

            # Group by week
            if week not in result["weeks"]:
                result["weeks"][week] = []
            result["weeks"][week].append(filename)
        except FileReadError as e:
            result["errors"].append(f"講義資料読み込みエラー ({filename}): {e}")
        except FileNotFoundError:
            result["errors"].append(f"ファイルが見つかりません: {filename}")
        except Exception as e:
            result["errors"].append(f"エラー ({filename}): {e}")

    if result["errors"]:
        result["success"] = False

    # Sort weeks
    result["weeks"] = dict(sorted(result["weeks"].items()))

    return result


def parse_all(syllabus_path: Path, lectures_folder: Path) -> dict:
    """Parse all files with auto-detected week numbers (original behavior)."""
    result = {
        "success": True,
        "mode": "auto",
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

    return result


def main():
    parser = argparse.ArgumentParser(description='Parse lecture files from a folder')
    parser.add_argument('syllabus', type=Path, help='Syllabus file path')
    parser.add_argument('folder', type=Path, help='Lectures folder path')
    parser.add_argument('--list-only', action='store_true', help='List files without reading content')
    parser.add_argument('--week-map', type=str, help='JSON mapping of filename to week number')
    parser.add_argument('--week', type=int, help='Week number for single week processing')
    parser.add_argument('--files', type=str, help='Comma-separated filenames for single week')

    args = parser.parse_args()

    if args.list_only:
        result = list_files_only(args.syllabus, args.folder)
    elif args.week and args.files:
        filenames = [f.strip() for f in args.files.split(',')]
        result = parse_single_week(args.syllabus, args.folder, args.week, filenames)
    elif args.week_map:
        week_map = json.loads(args.week_map)
        result = parse_with_week_map(args.syllabus, args.folder, week_map)
    else:
        result = parse_all(args.syllabus, args.folder)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
