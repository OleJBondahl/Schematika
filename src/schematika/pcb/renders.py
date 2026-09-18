"""3D and placement-drawing image export via kicad-cli.

Import this module directly (`from schematika.pcb.renders import ...`); it is
not re-exported from `schematika.pcb` because it imports Pillow at module
level, which the plain SKiDL-bridge callers of `schematika.pcb` shouldn't be
forced to install.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

from schematika.pcb.kicad_export import resolve_kicad_cli, run_kicad_cli

if TYPE_CHECKING:
    from pathlib import Path

_PLACEMENT_LAYERS = {
    "top": (["F.SilkS", "F.Fab", "Edge.Cuts"], False),
    "bottom": (["B.SilkS", "B.Fab", "Edge.Cuts"], True),
}


def crop_to_content(path: Path, margin_frac: float = 0.02) -> None:
    """Trim the transparent margin around a rendered board, keeping a small margin.

    Args:
        path: Image file to crop in place.
        margin_frac: Fraction of the content's own width/height kept as margin.
    """
    with Image.open(path) as im:
        bbox = im.getbbox()
        if bbox is None:
            return
        margin_x = round((bbox[2] - bbox[0]) * margin_frac)
        margin_y = round((bbox[3] - bbox[1]) * margin_frac)
        left = max(0, bbox[0] - margin_x)
        top = max(0, bbox[1] - margin_y)
        right = min(im.width, bbox[2] + margin_x)
        bottom = min(im.height, bbox[3] + margin_y)
        im.crop((left, top, right, bottom)).save(path)


def recolor_placement_svg(path: Path, *color_swaps: tuple[str, str]) -> None:
    """Replace each (old, new) color pair in an exported placement SVG's text.

    Args:
        path: SVG file to recolor in place.
        color_swaps: (from_color, to_color) hex-string pairs to substitute.
    """
    text = path.read_text(encoding="utf-8")
    for old, new in color_swaps:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def export_3d_render(
    pcb_path: Path,
    stem: str,
    side: str,
    output_dir: Path,
    *,
    width: str = "3600",
    height: str = "3600",
) -> Path:
    """Render a flat top/bottom 3D view of the board to a cropped PNG."""
    kicad_cli = resolve_kicad_cli()
    out_path = output_dir / f"{stem}_3d_{side}.png"
    run_kicad_cli(
        [
            str(kicad_cli),
            "pcb",
            "render",
            "--side",
            side,
            "--width",
            width,
            "--height",
            height,
            "--output",
            str(out_path),
            str(pcb_path),
        ]
    )
    crop_to_content(out_path)
    return out_path


def export_3d_iso_render(
    pcb_path: Path,
    stem: str,
    output_dir: Path,
    *,
    width: str = "4800",
    height: str = "2700",
) -> Path:
    """Render an isometric 3D view of the board to a cropped PNG."""
    kicad_cli = resolve_kicad_cli()
    out_path = output_dir / f"{stem}_3d_iso.png"
    run_kicad_cli(
        [
            str(kicad_cli),
            "pcb",
            "render",
            "--side",
            "top",
            "--rotate",
            "315,0,45",
            "--zoom",
            "1.15",
            "--width",
            width,
            "--height",
            height,
            "--output",
            str(out_path),
            str(pcb_path),
        ]
    )
    crop_to_content(out_path)
    return out_path


def export_placement_drawing(
    pcb_path: Path,
    stem: str,
    side: str,
    output_dir: Path,
    *,
    theme: str = "Documentation",
    color_swaps: tuple[tuple[str, str], ...] = (),
) -> Path:
    """Export one side's placement drawing (silkscreen+fab+edge) as SVG."""
    kicad_cli = resolve_kicad_cli()
    layers, mirror = _PLACEMENT_LAYERS[side]
    out_path = output_dir / f"{stem}_placement_{side}.svg"
    cmd = [
        str(kicad_cli),
        "pcb",
        "export",
        "svg",
        "--layers",
        ",".join(layers),
        "--fit-page-to-board",
        "--exclude-drawing-sheet",
        "--theme",
        theme,
        "--output",
        str(out_path),
    ]
    if mirror:
        cmd.append("--mirror")
    cmd.append(str(pcb_path))
    run_kicad_cli(cmd)
    if color_swaps:
        recolor_placement_svg(out_path, *color_swaps)
    return out_path
