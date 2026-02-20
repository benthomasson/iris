"""Tests for multiple dev task queue functionality in iris.

Tests the add_dev_task and list_dev_queues functions with:
- Basic queue routing (default, urgent, backlog)
- Backwards compatibility (default behavior, custom queue_path)
- Priority logic (queue_path overrides queue_name)
- Error handling (unknown queue names)
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch
import sys

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from iris import functions


class TestAddDevTask:
    """Tests for add_dev_task function."""

    def test_add_task_default_queue(self, tmp_path):
        """Test adding a task to the default queue."""
        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            result = functions.add_dev_task("fix the login bug")

            assert result["status"] == "added"
            assert result["task"] == "fix the login bug"
            assert result["queue_name"] == "default"
            assert "queue.txt" in result["queue_path"]

            # Verify file was written
            queue_file = tmp_path / "queue.txt"
            assert queue_file.exists()
            assert "fix the login bug\n" in queue_file.read_text()

    def test_add_task_urgent_queue(self, tmp_path):
        """Test adding a task to the urgent queue."""
        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            result = functions.add_dev_task("critical security fix", queue_name="urgent")

            assert result["status"] == "added"
            assert result["task"] == "critical security fix"
            assert result["queue_name"] == "urgent"
            assert "urgent.txt" in result["queue_path"]

            # Verify file was written to correct queue
            queue_file = tmp_path / "urgent.txt"
            assert queue_file.exists()
            assert "critical security fix\n" in queue_file.read_text()

    def test_add_task_backlog_queue(self, tmp_path):
        """Test adding a task to the backlog queue."""
        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            result = functions.add_dev_task("refactor the API layer", queue_name="backlog")

            assert result["status"] == "added"
            assert result["task"] == "refactor the API layer"
            assert result["queue_name"] == "backlog"
            assert "backlog.txt" in result["queue_path"]

            # Verify file was written
            queue_file = tmp_path / "backlog.txt"
            assert queue_file.exists()
            assert "refactor the API layer\n" in queue_file.read_text()

    def test_add_task_unknown_queue_returns_error(self, tmp_path):
        """Test that unknown queue names return a helpful error."""
        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            result = functions.add_dev_task("some task", queue_name="nonexistent")

            assert "error" in result
            assert "nonexistent" in result["error"]
            assert "default" in result["error"]
            assert "urgent" in result["error"]
            assert "backlog" in result["error"]

    def test_add_task_custom_queue_path(self, tmp_path):
        """Test adding a task with a custom queue_path."""
        custom_path = tmp_path / "my_custom_queue.txt"

        result = functions.add_dev_task("custom task", queue_path=str(custom_path))

        assert result["status"] == "added"
        assert result["task"] == "custom task"
        assert result["queue_name"] is None  # queue_name not used
        assert str(custom_path) == result["queue_path"]

        # Verify file was written
        assert custom_path.exists()
        assert "custom task\n" in custom_path.read_text()

    def test_queue_path_overrides_queue_name(self, tmp_path):
        """Test that queue_path takes priority over queue_name."""
        custom_path = tmp_path / "override.txt"

        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            result = functions.add_dev_task(
                "override task",
                queue_name="urgent",
                queue_path=str(custom_path)
            )

            # Should use queue_path, not queue_name
            assert result["status"] == "added"
            assert result["queue_name"] is None
            assert str(custom_path) == result["queue_path"]

            # Verify written to custom path, not urgent.txt
            assert custom_path.exists()
            assert "override task\n" in custom_path.read_text()
            assert not (tmp_path / "urgent.txt").exists()

    def test_backwards_compatibility_no_queue_name(self, tmp_path):
        """Test that calling with only task argument works (backwards compat)."""
        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            # This is how old code would call it
            result = functions.add_dev_task("legacy task")

            assert result["status"] == "added"
            assert result["queue_name"] == "default"
            assert "queue.txt" in result["queue_path"]

    def test_task_strip_whitespace(self, tmp_path):
        """Test that task whitespace is stripped."""
        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            result = functions.add_dev_task("  task with spaces  \n")

            assert result["task"] == "task with spaces"

            queue_file = tmp_path / "queue.txt"
            content = queue_file.read_text()
            assert content == "task with spaces\n"

    def test_multiple_tasks_append(self, tmp_path):
        """Test that multiple tasks are appended, not overwritten."""
        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            functions.add_dev_task("task 1")
            functions.add_dev_task("task 2")
            functions.add_dev_task("task 3")

            queue_file = tmp_path / "queue.txt"
            lines = queue_file.read_text().strip().split("\n")

            assert len(lines) == 3
            assert lines[0] == "task 1"
            assert lines[1] == "task 2"
            assert lines[2] == "task 3"


class TestListDevQueues:
    """Tests for list_dev_queues function."""

    def test_list_queues_empty(self, tmp_path):
        """Test listing queues when no queue files exist."""
        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            result = functions.list_dev_queues()

            assert "queues" in result
            assert len(result["queues"]) == 3  # default, urgent, backlog

            for queue in result["queues"]:
                assert "name" in queue
                assert "filename" in queue
                assert "path" in queue
                assert "task_count" in queue
                assert queue["task_count"] == 0  # No files exist yet

    def test_list_queues_with_tasks(self, tmp_path):
        """Test listing queues shows correct task counts."""
        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            # Add tasks to different queues
            functions.add_dev_task("default task 1")
            functions.add_dev_task("default task 2")
            functions.add_dev_task("urgent task", queue_name="urgent")

            result = functions.list_dev_queues()

            queues_by_name = {q["name"]: q for q in result["queues"]}

            assert queues_by_name["default"]["task_count"] == 2
            assert queues_by_name["urgent"]["task_count"] == 1
            assert queues_by_name["backlog"]["task_count"] == 0

    def test_list_queues_returns_all_required_fields(self, tmp_path):
        """Test that each queue entry has all required fields."""
        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            result = functions.list_dev_queues()

            for queue in result["queues"]:
                assert "name" in queue
                assert "filename" in queue
                assert "path" in queue
                assert "task_count" in queue

                # Verify filename matches expected pattern
                assert queue["filename"] in ["queue.txt", "urgent.txt", "backlog.txt"]

    def test_list_queues_correct_file_mapping(self, tmp_path):
        """Test that queue names map to correct filenames."""
        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            result = functions.list_dev_queues()

            queues_by_name = {q["name"]: q for q in result["queues"]}

            assert queues_by_name["default"]["filename"] == "queue.txt"
            assert queues_by_name["urgent"]["filename"] == "urgent.txt"
            assert queues_by_name["backlog"]["filename"] == "backlog.txt"

    def test_list_queues_ignores_blank_lines(self, tmp_path):
        """Test that blank lines are not counted as tasks."""
        with patch.object(functions, "DEV_QUEUE_BASE", tmp_path):
            # Create queue file with blank lines
            queue_file = tmp_path / "queue.txt"
            queue_file.write_text("task 1\n\ntask 2\n  \ntask 3\n")

            result = functions.list_dev_queues()
            queues_by_name = {q["name"]: q for q in result["queues"]}

            # Should count only non-blank lines
            assert queues_by_name["default"]["task_count"] == 3


class TestDevQueuesConstants:
    """Tests for queue constants."""

    def test_dev_queues_has_required_keys(self):
        """Test that DEV_QUEUES contains all required queue names."""
        assert "default" in functions.DEV_QUEUES
        assert "urgent" in functions.DEV_QUEUES
        assert "backlog" in functions.DEV_QUEUES

    def test_dev_queue_base_is_path(self):
        """Test that DEV_QUEUE_BASE is a Path object."""
        assert isinstance(functions.DEV_QUEUE_BASE, Path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
