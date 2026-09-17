"""pcb.kicad_export: fab-house package export via kicad-cli."""

import re
import zipfile
from pathlib import Path

import pytest

from schematika.pcb import kicad_export
from schematika.pcb.errors import PCBBuildError


def test_resolve_kicad_cli_found_on_path(monkeypatch):
    monkeypatch.setattr(
        kicad_export.shutil, "which", lambda _name: "C:/fake/kicad-cli.exe"
    )

    result = kicad_export.resolve_kicad_cli()

    assert result == Path("C:/fake/kicad-cli.exe")


def test_resolve_kicad_cli_found_via_glob_picks_highest_version(monkeypatch, tmp_path):
    monkeypatch.setattr(kicad_export.shutil, "which", lambda _name: None)
    (tmp_path / "9.0" / "bin").mkdir(parents=True)
    (tmp_path / "9.0" / "bin" / "kicad-cli.exe").touch()
    (tmp_path / "8.0" / "bin").mkdir(parents=True)
    (tmp_path / "8.0" / "bin" / "kicad-cli.exe").touch()

    result = kicad_export.resolve_kicad_cli(program_files_dir=tmp_path)

    assert result == tmp_path / "9.0" / "bin" / "kicad-cli.exe"


def test_resolve_kicad_cli_not_found_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(kicad_export.shutil, "which", lambda _name: None)

    with pytest.raises(kicad_export.KicadCliNotFoundError):
        kicad_export.resolve_kicad_cli(program_files_dir=tmp_path / "nowhere")


def test_kicad_cli_not_found_is_a_pcb_build_error():
    assert issubclass(kicad_export.KicadCliNotFoundError, PCBBuildError)


def test_run_kicad_cli_raises_on_nonzero_exit(monkeypatch):
    class _FakeResult:
        returncode = 1
        stderr = "boom"

    monkeypatch.setattr(kicad_export.subprocess, "run", lambda *_a, **_k: _FakeResult())

    with pytest.raises(kicad_export.KicadCliCommandError, match="boom"):
        kicad_export.run_kicad_cli(["kicad-cli", "pcb", "export", "gerbers"])


def test_export_production_package_requires_bom(tmp_path):
    with pytest.raises(FileNotFoundError, match=re.escape("bom.xlsx")):
        kicad_export.export_production_package(
            tmp_path / "board.kicad_pcb",
            "board",
            "v01",
            tmp_path,
            bom_path=tmp_path / "bom.xlsx",
            production_doc_path=tmp_path / "manual.pdf",
        )


def test_export_production_package_requires_production_doc(tmp_path):
    bom_path = tmp_path / "bom.xlsx"
    bom_path.write_text("bom", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match=re.escape("manual.pdf")):
        kicad_export.export_production_package(
            tmp_path / "board.kicad_pcb",
            "board",
            "v01",
            tmp_path,
            bom_path=bom_path,
            production_doc_path=tmp_path / "manual.pdf",
        )


def test_export_production_package_builds_single_top_level_zip(tmp_path, monkeypatch):
    pcb_path = tmp_path / "board.kicad_pcb"
    pcb_path.write_text("(kicad_pcb)", encoding="utf-8")
    bom_path = tmp_path / "bom.xlsx"
    bom_path.write_text("bom", encoding="utf-8")
    doc_path = tmp_path / "manual.pdf"
    doc_path.write_text("pdf", encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    monkeypatch.setattr(
        kicad_export, "resolve_kicad_cli", lambda **_k: Path("kicad-cli")
    )

    calls: list[list[str]] = []

    def fake_run(cmd: list[str]) -> None:
        calls.append(cmd)
        out = Path(cmd[cmd.index("--output") + 1])
        if out.suffix:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"fake")
        else:
            out.mkdir(parents=True, exist_ok=True)
            (out / "board-F_Cu.gbr").write_bytes(b"fake")

    monkeypatch.setattr(kicad_export, "run_kicad_cli", fake_run)

    zip_path = kicad_export.export_production_package(
        pcb_path,
        "board",
        "v01",
        output_dir,
        bom_path=bom_path,
        production_doc_path=doc_path,
    )

    assert zip_path == output_dir / "board_production_files_v01.zip"
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        top_level = {n.split("/")[0] for n in names}
    assert top_level == {"board_production_files_v01"}
    assert any(n.endswith("board-F_Cu_v01.gbr") for n in names)
    assert any(n.endswith("board_BOM_v01.xlsx") for n in names)
    assert any(n.endswith("manual.pdf") for n in names)
    assert [c[3] for c in calls] == ["gerbers", "drill", "pos", "step"]
    assert not (output_dir / "board_production_files_v01").exists()
