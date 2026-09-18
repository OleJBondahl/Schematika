"""KiCad fab-house export: gerbers, drill, pick-and-place, STEP, and packaging.

Requires the `kicad-cli` binary (bundled with the KiCad desktop app) on PATH
or under KiCad's default Windows install directory -- it is not a PyPI
package, so it isn't declared as an extra. Import this module directly
(`from schematika.pcb.kicad_export import ...`); it is not re-exported from
`schematika.pcb`.
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

from schematika.pcb.errors import PCBBuildError

_KICAD_PROGRAM_FILES_DIR = Path("C:/Program Files/KiCad")


class KicadCliNotFoundError(PCBBuildError):
    """kicad-cli is not on PATH and not found under the usual install directory."""

    def __init__(self, search_dir: Path) -> None:
        """Capture the searched install directory for the error message."""
        self.search_dir = search_dir
        super().__init__(
            f"kicad-cli not found on PATH or under '{search_dir}/*/bin/kicad-cli.exe'. "
            "Install KiCad (https://www.kicad.org/download/) or add kicad-cli to PATH."
        )


class KicadCliCommandError(PCBBuildError):
    """A kicad-cli invocation exited non-zero."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str) -> None:
        """Capture the failed command, exit code, and stderr for the message."""
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"command failed ({returncode}): {' '.join(cmd)}\n{stderr}")


def resolve_kicad_cli(*, program_files_dir: Path = _KICAD_PROGRAM_FILES_DIR) -> Path:
    """Find the kicad-cli binary on PATH or under KiCad's default install dir.

    Args:
        program_files_dir: Base directory to search for a versioned KiCad
            install (e.g. `C:/Program Files/KiCad/9.0/bin/kicad-cli.exe`).

    Returns:
        Path to the resolved kicad-cli executable.

    Raises:
        KicadCliNotFoundError: kicad-cli isn't on PATH or under `program_files_dir`.
    """
    found = shutil.which("kicad-cli")
    if found:
        return Path(found)
    candidates = sorted(
        program_files_dir.glob("*/bin/kicad-cli.exe"), key=_version_key, reverse=True
    )
    if candidates:
        return candidates[0]
    raise KicadCliNotFoundError(program_files_dir)


def _version_key(path: Path) -> tuple[int, ...]:
    """Sort key for a `<version>/bin/kicad-cli.exe` glob match by numeric version.

    Raw string sort would rank "9.0" above "10.0"; this parses the version
    directory (the glob match's third-from-last path part) into an int tuple
    so "10.0" correctly outranks "9.0".
    """
    version_str = path.parts[-3]
    return tuple(int(p) if p.isdigit() else -1 for p in version_str.split("."))


def run_kicad_cli(cmd: list[str]) -> None:
    """Run a kicad-cli subprocess command, raising on non-zero exit.

    Args:
        cmd: Full argv, including the resolved kicad-cli path as `cmd[0]`.

    Raises:
        KicadCliCommandError: the command exited non-zero.
    """
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603 -- fixed argv built from resolved paths, no untrusted input
    if result.returncode != 0:
        raise KicadCliCommandError(cmd, result.returncode, result.stderr)


def export_production_package(
    pcb_path: Path,
    stem: str,
    version: str,
    output_dir: Path,
    *,
    bom_path: Path,
    production_doc_path: Path,
) -> Path:
    """Export gerbers/drill/pos/step, bundle with the BOM+manual, and zip.

    Args:
        pcb_path: Path to the `.kicad_pcb` board file.
        stem: Base filename stem for every exported file (e.g. "juicebox_pcb").
        version: Production package version tag, stamped into every filename.
        output_dir: Directory the final zip is written into.
        bom_path: Path to the already-generated BOM XLSX to bundle.
        production_doc_path: Path to the already-generated production manual
            PDF to bundle.

    Returns:
        Path to the written zip file.

    Raises:
        FileNotFoundError: `bom_path` or `production_doc_path` doesn't exist yet.
        KicadCliNotFoundError: kicad-cli isn't installed/on PATH.
        KicadCliCommandError: a kicad-cli export command failed.
    """
    if not bom_path.exists():
        msg = f"{bom_path} does not exist -- generate the BOM before exporting"
        raise FileNotFoundError(msg)
    if not production_doc_path.exists():
        msg = (
            f"{production_doc_path} does not exist -- "
            "generate the production doc before exporting"
        )
        raise FileNotFoundError(msg)

    kicad_cli = resolve_kicad_cli()
    staging = output_dir / f"{stem}_production_files_{version}"
    gerber_dir = staging / f"{stem}_gerber_{version}"
    shutil.rmtree(staging, ignore_errors=True)
    gerber_dir.mkdir(parents=True, exist_ok=True)

    run_kicad_cli(
        [
            str(kicad_cli),
            "pcb",
            "export",
            "gerbers",
            "--output",
            str(gerber_dir),
            str(pcb_path),
        ]
    )
    run_kicad_cli(
        [
            str(kicad_cli),
            "pcb",
            "export",
            "drill",
            "--output",
            str(gerber_dir),
            str(pcb_path),
        ]
    )
    for gerber_file in list(gerber_dir.iterdir()):
        if gerber_file.is_file():
            gerber_file.rename(
                gerber_file.with_name(
                    f"{gerber_file.stem}_{version}{gerber_file.suffix}"
                )
            )
    pos_path = staging / f"{stem}_Pick-n-Place-top_{version}.csv"
    run_kicad_cli(
        [
            str(kicad_cli),
            "pcb",
            "export",
            "pos",
            "--side",
            "front",
            "--format",
            "csv",
            "--units",
            "mm",
            "--output",
            str(pos_path),
            str(pcb_path),
        ]
    )
    step_path = staging / f"{stem}_{version}.step"
    run_kicad_cli(
        [
            str(kicad_cli),
            "pcb",
            "export",
            "step",
            "--output",
            str(step_path),
            str(pcb_path),
        ]
    )

    shutil.copy2(bom_path, staging / f"{stem}_BOM_{version}.xlsx")
    shutil.copy2(production_doc_path, staging / production_doc_path.name)

    zip_path = output_dir / f"{stem}_production_files_{version}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in staging.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, arcname=file_path.relative_to(staging.parent))
    shutil.rmtree(staging)
    return zip_path
