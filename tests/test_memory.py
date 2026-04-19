"""Tests for memory entry writing."""

from lib.memory import write_memory_entry, update_memory_index


class TestWriteMemoryEntry:
    def test_writes_frontmatter_format(self, tmp_memory_dir):
        write_memory_entry(
            memory_dir=tmp_memory_dir,
            filename="retro_feedback_testing.md",
            name="Testing approach",
            description="Always use integration tests for database code",
            memory_type="feedback",
            body="Don't mock the database in integration tests.\n\n"
                 "**Why:** Prior incident where mock/prod diverged.\n\n"
                 "**How to apply:** Use test database for all DB-touching tests.",
        )
        path = tmp_memory_dir / "retro_feedback_testing.md"
        assert path.exists()
        content = path.read_text()
        assert "---" in content
        assert "name: Testing approach" in content
        assert "type: feedback" in content
        assert "Don't mock the database" in content

    def test_overwrites_existing(self, tmp_memory_dir):
        write_memory_entry(tmp_memory_dir, "test.md", "v1", "d", "feedback", "old")
        write_memory_entry(tmp_memory_dir, "test.md", "v2", "d", "feedback", "new")
        content = (tmp_memory_dir / "test.md").read_text()
        assert "v2" in content
        assert "old" not in content


class TestUpdateMemoryIndex:
    def test_creates_memory_md_if_missing(self, tmp_memory_dir):
        update_memory_index(
            tmp_memory_dir, "test_file.md", "Test entry description"
        )
        index = tmp_memory_dir / "MEMORY.md"
        assert index.exists()
        content = index.read_text()
        assert "[Test entry description](test_file.md)" in content

    def test_appends_to_existing_index(self, tmp_memory_dir):
        (tmp_memory_dir / "MEMORY.md").write_text(
            "- [Existing](existing.md) - old entry\n"
        )
        update_memory_index(tmp_memory_dir, "new.md", "New entry")
        content = (tmp_memory_dir / "MEMORY.md").read_text()
        assert "Existing" in content
        assert "New entry" in content

    def test_does_not_duplicate(self, tmp_memory_dir):
        update_memory_index(tmp_memory_dir, "test.md", "Test")
        update_memory_index(tmp_memory_dir, "test.md", "Test updated")
        content = (tmp_memory_dir / "MEMORY.md").read_text()
        assert content.count("test.md") == 1
