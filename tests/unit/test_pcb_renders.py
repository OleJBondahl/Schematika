"""pcb.renders: 3D and placement-drawing image export via kicad-cli."""

from pathlib import Path

from PIL import Image

from schematika.pcb import renders


def test_crop_to_content_trims_transparent_margin(tmp_path):
    im = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(40, 60):
        for y in range(40, 60):
            im.putpixel((x, y), (0, 128, 0, 255))
    path = tmp_path / "test.png"
    im.save(path)

    renders.crop_to_content(path, margin_frac=0.0)

    with Image.open(path) as cropped:
        assert cropped.size == (20, 20)


def test_crop_to_content_adds_margin(tmp_path):
    im = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(40, 60):
        for y in range(40, 60):
            im.putpixel((x, y), (0, 128, 0, 255))
    path = tmp_path / "test.png"
    im.save(path)

    renders.crop_to_content(path, margin_frac=0.1)

    with Image.open(path) as cropped:
        assert cropped.size == (24, 24)


def test_recolor_placement_svg_applies_given_swaps(tmp_path):
    path = tmp_path / "test.svg"
    path.write_text(
        '<path style="stroke:#AFAFAF;fill:#000000"/><path style="stroke:#D0D2CD"/>',
        encoding="utf-8",
    )

    renders.recolor_placement_svg(path, ("#AFAFAF", "#1F5FA8"), ("#D0D2CD", "#C0392B"))

    text = path.read_text(encoding="utf-8")
    assert "#AFAFAF" not in text
    assert "#D0D2CD" not in text
    assert "#1F5FA8" in text
    assert "#C0392B" in text
    assert "#000000" in text


def test_export_3d_render_writes_expected_path(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(renders, "resolve_kicad_cli", lambda **_k: Path("kicad-cli"))
    monkeypatch.setattr(renders, "run_kicad_cli", lambda cmd: calls.append(cmd))
    monkeypatch.setattr(renders, "crop_to_content", lambda _path: None)

    out_path = renders.export_3d_render(
        Path("board.kicad_pcb"), "board", "top", tmp_path
    )

    assert out_path == tmp_path / "board_3d_top.png"
    cmd = calls[0]
    assert cmd[cmd.index("--side") + 1] == "top"
    assert cmd[cmd.index("--output") + 1] == str(out_path)
    assert cmd[cmd.index("--width") + 1] == "3600"


def test_export_3d_iso_render_writes_expected_path(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(renders, "resolve_kicad_cli", lambda **_k: Path("kicad-cli"))
    monkeypatch.setattr(renders, "run_kicad_cli", lambda cmd: calls.append(cmd))
    monkeypatch.setattr(renders, "crop_to_content", lambda _path: None)

    out_path = renders.export_3d_iso_render(Path("board.kicad_pcb"), "board", tmp_path)

    assert out_path == tmp_path / "board_3d_iso.png"
    cmd = calls[0]
    assert cmd[cmd.index("--rotate") + 1] == "315,0,45"
    assert cmd[cmd.index("--zoom") + 1] == "1.15"


def test_export_placement_drawing_top_uses_front_layers_no_mirror(
    tmp_path, monkeypatch
):
    calls: list[list[str]] = []
    monkeypatch.setattr(renders, "resolve_kicad_cli", lambda **_k: Path("kicad-cli"))
    monkeypatch.setattr(renders, "run_kicad_cli", lambda cmd: calls.append(cmd))

    out_path = renders.export_placement_drawing(
        Path("board.kicad_pcb"), "board", "top", tmp_path
    )

    assert out_path == tmp_path / "board_placement_top.svg"
    cmd = calls[0]
    assert cmd[cmd.index("--layers") + 1] == "F.SilkS,F.Fab,Edge.Cuts"
    assert "--mirror" not in cmd


def test_export_placement_drawing_bottom_mirrors(tmp_path, monkeypatch):
    monkeypatch.setattr(renders, "resolve_kicad_cli", lambda **_k: Path("kicad-cli"))
    monkeypatch.setattr(renders, "run_kicad_cli", lambda cmd: None)

    renders.export_placement_drawing(
        Path("board.kicad_pcb"), "board", "bottom", tmp_path
    )


def test_export_placement_drawing_applies_color_swaps(tmp_path, monkeypatch):
    def fake_run(cmd: list[str]) -> None:
        out = Path(cmd[cmd.index("--output") + 1])
        out.write_text('<path style="stroke:#AFAFAF"/>', encoding="utf-8")

    monkeypatch.setattr(renders, "resolve_kicad_cli", lambda **_k: Path("kicad-cli"))
    monkeypatch.setattr(renders, "run_kicad_cli", fake_run)

    out_path = renders.export_placement_drawing(
        Path("board.kicad_pcb"),
        "board",
        "top",
        tmp_path,
        color_swaps=(("#AFAFAF", "#1F5FA8"),),
    )

    assert "#1F5FA8" in out_path.read_text(encoding="utf-8")
