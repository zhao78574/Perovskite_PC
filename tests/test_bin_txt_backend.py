from pathlib import Path
import base64
import struct

import build_exe


class FolderDialog:
    def __init__(self, folder: Path):
        self.folder = folder

    def create_file_dialog(self, *_args, **_kwargs):
        return [str(self.folder)]


class DialogSequence:
    def __init__(self, *results):
        self.results = iter(results)

    def create_file_dialog(self, *_args, **_kwargs):
        return next(self.results)


def test_save_png_decodes_data_url(tmp_path):
    output = tmp_path / "plot.png"
    build_exe.window = FolderDialog(output)
    build_exe.window.create_file_dialog = lambda *_args, **_kwargs: [str(output)]
    payload = b"\x89PNG\r\n\x1a\n"
    result = build_exe.BackendAPI().save_png_python("plot.png", "data:image/png;base64," + base64.b64encode(payload).decode())
    assert result == "success"
    assert output.read_bytes() == payload


def test_save_plot_supports_svg_and_png(tmp_path):
    api = build_exe.BackendAPI()
    svg_output = tmp_path / "plot.svg"
    build_exe.window = FolderDialog(svg_output)
    build_exe.window.create_file_dialog = lambda *_args, **_kwargs: [str(svg_output)]
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><text>J–V</text></svg>'
    assert api.save_plot_python("plot.svg", "data:image/svg+xml," + svg.replace('–', '%E2%80%93')) == "success"
    assert svg_output.read_text(encoding="utf-8") == svg

    png_output = tmp_path / "plot.png"
    build_exe.window.create_file_dialog = lambda *_args, **_kwargs: [str(png_output)]
    payload = b"\x89PNG\r\n\x1a\n"
    encoded = base64.b64encode(payload).decode()
    assert api.save_plot_python("plot.png", "data:image/png;base64," + encoded) == "success"
    assert png_output.read_bytes() == payload


def test_save_plot_rejects_unsupported_extensions(tmp_path):
    assert build_exe.BackendAPI().save_plot_python("plot.pdf", "data:application/pdf;base64,AA==").startswith("error:")


def test_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    build_exe.window = FolderDialog(path)
    build_exe.window.create_file_dialog = lambda *_args, **_kwargs: [str(path)]
    api = build_exe.BackendAPI()
    settings = {"format": "perovskite-workstation-settings", "version": 1, "values": {"pce-area": "0.1"}}

    assert api.save_settings_python(settings) == "success"
    assert api.load_settings_python() == {"status": "success", "settings": settings}


def test_settings_loader_rejects_unrelated_json(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"hello": "world"}', encoding="utf-8")
    build_exe.window = FolderDialog(path)

    result = build_exe.BackendAPI().load_settings_python()

    assert result["status"] == "error"
    assert "不是受支持" in result["message"]


def test_save_text_files_avoids_overwrite(tmp_path):
    build_exe.window = FolderDialog(tmp_path)
    existing = tmp_path / "sample.txt"
    existing.write_text("original", encoding="utf-8")

    result = build_exe.BackendAPI().save_text_files_python([
        {"name": "sample.txt", "content": "Potential_V\tCurrent_A\n0\t0.002"}
    ], ["broken.bin"])

    assert result == "success:1"
    assert existing.read_text(encoding="utf-8") == "original"
    assert (tmp_path / "sample (1).txt").read_text(encoding="utf-8") == "Potential_V\tCurrent_A\n0\t0.002"
    report = (tmp_path / "BIN转换失败记录.txt").read_text(encoding="utf-8-sig")
    assert "失败文件数: 1" in report
    assert "broken.bin\t无法识别为受支持的 CHI LSV 文件" in report


def test_convert_chi_bin_file(tmp_path):
    source = tmp_path / "sample.bin"
    payload = bytearray(1453)
    payload[8:11] = b'LSV'
    struct.pack_into('<f', payload, 853, 1.2)
    struct.pack_into('<f', payload, 857, 0.0)
    struct.pack_into('<f', payload, 885, 0.4)
    source.write_bytes(payload + struct.pack('<fff', -0.002, -0.001, 0.001))
    output = tmp_path / "sample.txt"

    assert build_exe.convert_chi_bin_file(source, output)
    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines[1:8] == [
        "Technique: Linear Sweep Voltammetry (LSV)", "Points: 3", "Potential start (V): 1.2",
        "Potential end (V): 0.4", "Potential step (V): -0.4", "", "Potential (V)\tCurrent (A)"
    ]
    assert lines[8:] == ["1.2\t-2.000000095e-03", "0.8\t-1.000000047e-03", "0.4\t1.000000047e-03"]


def test_convert_folder_recursively_preserves_subfolders(tmp_path):
    source = tmp_path / "source"
    nested = source / "20240418"
    output = tmp_path / "output"
    nested.mkdir(parents=True)
    output.mkdir()
    payload = bytearray(1453)
    payload[8:11] = b'LSV'
    struct.pack_into('<f', payload, 853, 0.5)
    struct.pack_into('<f', payload, 857, 0.0)
    struct.pack_into('<f', payload, 885, 0.5)
    (nested / "measurement.bin").write_bytes(payload + struct.pack('<f', 0.001))
    build_exe.window = DialogSequence([str(source)], [str(output)])

    result = build_exe.BackendAPI().convert_bin_folders_python()

    assert result == {"status": "success", "converted": 1, "failed": 0}
    assert (output / "20240418" / "measurement.txt").exists()


def test_recursive_conversion_writes_failure_report(tmp_path):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (source / "broken.bin").write_bytes(b'not a CHI file')
    build_exe.window = DialogSequence([str(source)], [str(output)])

    result = build_exe.BackendAPI().convert_bin_folders_python()

    assert result == {"status": "success", "converted": 0, "failed": 1}
    report = (output / "BIN转换失败记录.txt").read_text(encoding="utf-8-sig")
    assert "broken.bin" in report
    assert "不是受支持的 CHI LSV 文件" in report
