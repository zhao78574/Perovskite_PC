from pathlib import Path

import build_exe


class FolderDialog:
    def __init__(self, folder: Path):
        self.folder = folder

    def create_file_dialog(self, *_args, **_kwargs):
        return [str(self.folder)]


def test_rename_requires_preview_and_can_be_undone(tmp_path):
    (tmp_path / "sample.txt").write_text("data", encoding="utf-8")
    build_exe.window = FolderDialog(tmp_path)
    api = build_exe.BackendAPI()

    assert api.execute_rename_python()["status"] == "error"
    preview = api.preview_rename_python("1", "run-")
    assert preview == {
        "status": "success",
        "folder": str(tmp_path),
        "operations": [{"old": "sample.txt", "new": "run-sample.txt"}],
        "conflicts": [],
    }
    assert (tmp_path / "sample.txt").exists()

    assert api.execute_rename_python() == {"status": "success", "count": 1}
    assert not (tmp_path / "sample.txt").exists()
    assert (tmp_path / "run-sample.txt").exists()

    assert api.undo_rename_python() == {"status": "success", "count": 1}
    assert (tmp_path / "sample.txt").exists()
    assert not (tmp_path / "run-sample.txt").exists()


def test_preview_blocks_existing_targets(tmp_path):
    (tmp_path / "sample.txt").write_text("source", encoding="utf-8")
    (tmp_path / "run-sample.txt").write_text("keep", encoding="utf-8")
    build_exe.window = FolderDialog(tmp_path)
    api = build_exe.BackendAPI()

    preview = api.preview_rename_python("1", "run-")
    assert "run-sample.txt" in preview["conflicts"]
    assert api.execute_rename_python()["status"] == "error"
    assert (tmp_path / "run-sample.txt").read_text(encoding="utf-8") == "keep"


def test_failure_rolls_back_completed_files(tmp_path, monkeypatch):
    for name in ("a.txt", "b.txt"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    build_exe.window = FolderDialog(tmp_path)
    api = build_exe.BackendAPI()
    api.preview_rename_python("1", "run-")
    real_rename = build_exe.os.rename
    calls = 0

    def fail_second(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated failure")
        real_rename(source, target)

    monkeypatch.setattr(build_exe.os, "rename", fail_second)
    result = api.execute_rename_python()

    assert result["status"] == "error"
    assert (tmp_path / "a.txt").exists()
    assert (tmp_path / "b.txt").exists()
    assert not (tmp_path / "run-a.txt").exists()
