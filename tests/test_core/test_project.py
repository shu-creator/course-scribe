"""Tests for project management module."""

import pytest
import json
from pathlib import Path
from course_scribe.core.project import (
    init_project,
    find_project_root,
    load_config,
    save_config,
    load_syllabus,
    save_syllabus,
    add_lecture_record,
    get_output_path,
    project_exists,
    ProjectConfig,
    ProjectNotFoundError,
    ProjectExistsError,
    PROJECT_DIR,
)


@pytest.fixture
def sample_syllabus():
    """Sample syllabus data."""
    return {
        "course_name": "Test Course",
        "instructor": "Test Instructor",
        "description": "A test course",
        "weeks": [
            {"week_number": 1, "title": "Week 1", "topics": ["Topic A"], "keywords": ["keyword1"], "learning_objectives": []},
            {"week_number": 2, "title": "Week 2", "topics": ["Topic B"], "keywords": ["keyword2"], "learning_objectives": []},
        ],
        "total_weeks": 2,
    }


class TestInitProject:
    def test_creates_project_directory(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")

        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        assert (tmp_path / PROJECT_DIR).exists()
        assert (tmp_path / PROJECT_DIR).is_dir()

    def test_creates_config_file(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")

        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        config_path = tmp_path / PROJECT_DIR / "config.json"
        assert config_path.exists()

    def test_saves_syllabus(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")

        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        syllabus_json = tmp_path / PROJECT_DIR / "syllabus.json"
        assert syllabus_json.exists()
        loaded = json.loads(syllabus_json.read_text())
        assert loaded["course_name"] == "Test Course"

    def test_raises_if_project_exists(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")

        # First init should succeed
        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        # Second init should fail
        with pytest.raises(ProjectExistsError):
            init_project(syllabus_path, sample_syllabus, root=tmp_path)


class TestFindProjectRoot:
    def test_finds_project_in_current_dir(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")
        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        root = find_project_root(tmp_path)
        assert root == tmp_path

    def test_finds_project_in_parent_dir(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")
        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        # Create and search from subdirectory
        subdir = tmp_path / "subdir" / "deep"
        subdir.mkdir(parents=True)

        root = find_project_root(subdir)
        assert root == tmp_path

    def test_raises_if_no_project(self, tmp_path):
        with pytest.raises(ProjectNotFoundError):
            find_project_root(tmp_path)


class TestLoadSaveSyllabus:
    def test_save_and_load_syllabus(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")
        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        loaded = load_syllabus(tmp_path)
        assert loaded["course_name"] == sample_syllabus["course_name"]
        assert loaded["total_weeks"] == sample_syllabus["total_weeks"]


class TestLoadSaveConfig:
    def test_save_and_load_config(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")
        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        config = load_config(tmp_path)
        assert config.course_name == "Test Course"
        assert config.syllabus_source == str(syllabus_path)


class TestAddLectureRecord:
    def test_adds_new_lecture(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")
        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        add_lecture_record(
            week_number=1,
            source_file="lecture_01.pptx",
            has_summary=True,
            has_questions=True,
            root=tmp_path,
        )

        config = load_config(tmp_path)
        assert len(config.lectures) == 1
        assert config.lectures[0].week_number == 1

    def test_updates_existing_lecture(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")
        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        # Add first time
        add_lecture_record(week_number=1, source_file="old.pptx", root=tmp_path)
        # Update
        add_lecture_record(week_number=1, source_file="new.pptx", root=tmp_path)

        config = load_config(tmp_path)
        assert len(config.lectures) == 1
        assert config.lectures[0].source_file == "new.pptx"

    def test_sorts_lectures_by_week(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")
        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        # Add out of order
        add_lecture_record(week_number=3, source_file="lec3.pptx", root=tmp_path)
        add_lecture_record(week_number=1, source_file="lec1.pptx", root=tmp_path)
        add_lecture_record(week_number=2, source_file="lec2.pptx", root=tmp_path)

        config = load_config(tmp_path)
        weeks = [lec.week_number for lec in config.lectures]
        assert weeks == [1, 2, 3]


class TestProjectExists:
    def test_returns_true_when_exists(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")
        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        assert project_exists(tmp_path) is True

    def test_returns_false_when_not_exists(self, tmp_path):
        assert project_exists(tmp_path) is False


class TestGetOutputPath:
    def test_returns_output_directory(self, tmp_path, sample_syllabus):
        syllabus_path = tmp_path / "syllabus.txt"
        syllabus_path.write_text("test")
        init_project(syllabus_path, sample_syllabus, root=tmp_path)

        output_path = get_output_path(tmp_path)
        assert output_path == tmp_path / "output"
