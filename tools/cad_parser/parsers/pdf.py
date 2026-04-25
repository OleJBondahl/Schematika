"""PDF schematic parser for the cad_parser tool.

Converts each PDF page to SVG using PyMuPDF (``fitz``) and delegates
geometry extraction to :class:`SvgParser`.  Multi-page results are merged
into a single :class:`SchematicData` with page-prefixed wire IDs to avoid
ID collisions.

Requires PyMuPDF::

    pip install pymupdf

If PyMuPDF is not installed, importing this module will succeed but calling
:meth:`PdfParser.parse` will raise :exc:`ImportError` with a clear message.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from ..models import Metadata, SchematicData, WireInfo
from .svg import SvgParser

log = logging.getLogger(__name__)


class PdfParser:
    """Parse a PDF schematic file into :class:`SchematicData`.

    Each page is converted to an SVG string via PyMuPDF, written to a
    temporary file, and parsed by :class:`SvgParser`.  The per-page results
    are then merged: component and terminal lists are concatenated, and wire
    IDs are prefixed with the 1-based page number (``W3_p2`` = wire 3 on
    page 2) to prevent clashes across pages.
    """

    def parse(self, path: Path) -> SchematicData:
        try:
            import fitz  # PyMuPDF  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "PyMuPDF is required for PDF parsing. "
                "Install it with: pip install pymupdf"
            ) from exc

        log.debug("Opening PDF: %s", path)
        try:
            doc = fitz.open(str(path))
        except Exception as exc:
            log.error("Failed to open PDF %s: %s", path, exc)
            raise

        if doc.is_encrypted:
            log.warning("PDF %s is encrypted/password-protected; cannot parse", path)
            doc.close()
            return SchematicData(
                metadata=Metadata(
                    source_format="pdf",
                    filename=path.name,
                    pages=0,
                )
            )

        page_count = doc.page_count
        log.debug("PDF has %d page(s)", page_count)

        merged = SchematicData(
            metadata=Metadata(
                source_format="pdf",
                filename=path.name,
                pages=page_count,
            )
        )

        svg_parser = SvgParser()

        for page_num in range(page_count):
            page = doc[page_num]
            label = page_num + 1  # 1-based for display and ID prefixing

            log.debug("Processing page %d/%d", label, page_count)

            try:
                svg_content = page.get_svg_image()
            except AttributeError:
                log.warning(
                    "Page %d: get_svg_image() not available (old PyMuPDF); "
                    "falling back to direct extraction",
                    label,
                )
                page_data = self._parse_page_direct(page, path, label)
            except Exception as exc:
                log.warning("Page %d: SVG export failed (%s); skipping", label, exc)
                continue
            else:
                if not svg_content or not svg_content.strip():
                    log.warning(
                        "Page %d: SVG export returned empty content; skipping", label
                    )
                    continue
                page_data = self._parse_svg_content(
                    svg_content, svg_parser, path, label
                )

            if page_data is None:
                continue

            self._merge_page(merged, page_data, label)

        doc.close()

        log.info(
            "Parsed %s: %d page(s), %d components, %d wires, %d terminals, %d nets",
            path.name,
            page_count,
            len(merged.components),
            len(merged.wires),
            len(merged.terminals),
            len(merged.nets),
        )

        return merged

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_svg_content(
        self,
        svg_content: str,
        svg_parser: SvgParser,
        source_path: Path,
        page_num: int,
    ) -> SchematicData | None:
        """Write SVG content to a temp file and parse it with SvgParser."""
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".svg",
                delete=False,
                mode="w",
                encoding="utf-8",
            ) as tmp:
                tmp.write(svg_content)
                tmp_path = Path(tmp.name)

            log.debug(
                "Page %d: wrote %d bytes to temp SVG %s",
                page_num,
                len(svg_content),
                tmp_path,
            )

            page_data = svg_parser.parse(tmp_path)
            return page_data

        except Exception as exc:
            log.warning("Page %d: SvgParser failed (%s); skipping", page_num, exc)
            return None
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _parse_page_direct(
        self, page: object, source_path: Path, page_num: int
    ) -> SchematicData | None:
        """Fallback: extract geometry directly using PyMuPDF drawing/text APIs.

        Used when ``page.get_svg_image()`` is unavailable (old PyMuPDF).
        Extracts line segments from ``page.get_drawings()`` and text from
        ``page.get_text("dict")``.  Wire connectivity heuristics are not
        applied; this is a best-effort result.
        """
        from ..models import Metadata, SchematicData  # noqa: PLC0415

        try:
            drawings = page.get_drawings()  # type: ignore[attr-defined]
        except Exception as exc:
            log.warning("Page %d: get_drawings() failed (%s)", page_num, exc)
            drawings = []

        try:
            text_dict = page.get_text("dict")  # type: ignore[attr-defined]
        except Exception as exc:
            log.warning("Page %d: get_text() failed (%s)", page_num, exc)
            text_dict = {"blocks": []}

        if not drawings and not text_dict.get("blocks"):
            log.warning("Page %d: no vector data or text; skipping", page_num)
            return None

        raw_segments = self._drawings_to_segments(drawings)
        raw_texts = self._textdict_to_texts(text_dict)
        components = self._texts_to_components(raw_texts)
        wires = self._segments_to_wires(raw_segments)
        terminals = self._components_to_terminals(components)

        log.debug(
            "Page %d direct: %d components, %d wire segments, %d terminals",
            page_num,
            len(components),
            len(wires),
            len(terminals),
        )

        return SchematicData(
            metadata=Metadata(
                source_format="pdf",
                filename=source_path.name,
                pages=1,
            ),
            components=components,
            wires=wires,
            terminals=terminals,
            nets=[],
        )

    def _drawings_to_segments(self, drawings: list) -> list:
        """Convert PyMuPDF drawing items to WireSegment objects."""
        from ..models import Position, WireSegment  # noqa: PLC0415

        segments: list[WireSegment] = []
        for drawing in drawings:
            for item in drawing.get("items", []):
                if item[0] == "l":  # line: (type, p1, p2)
                    p1, p2 = item[1], item[2]
                    segments.append(
                        WireSegment(
                            start=Position(x=float(p1.x), y=float(p1.y)),
                            end=Position(x=float(p2.x), y=float(p2.y)),
                        )
                    )
        return segments

    def _textdict_to_texts(self, text_dict: dict) -> list:
        """Flatten PyMuPDF text dict into (content, Position) pairs."""
        from ..models import Position  # noqa: PLC0415

        texts: list[tuple[str, Position]] = []
        for block in text_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    content = span.get("text", "").strip()
                    if not content:
                        continue
                    origin = span.get("origin", (0.0, 0.0))
                    texts.append((content, Position(x=origin[0], y=origin[1])))
        return texts

    def _texts_to_components(self, raw_texts: list) -> list:
        """Build ComponentInfo list from reference-pattern text matches."""
        import re  # noqa: PLC0415

        from ..models import ComponentInfo  # noqa: PLC0415
        from ..utils import normalize_component_type  # noqa: PLC0415

        _REF_PATTERN = re.compile(r"^[A-Z]{1,3}\d+$")
        components: list[ComponentInfo] = []
        seen: set[str] = set()
        for text, pos in raw_texts:
            if not _REF_PATTERN.match(text) or text in seen:
                continue
            seen.add(text)
            m = re.match(r"^([A-Z]{1,3})", text)
            prefix = m.group(1) if m else ""
            components.append(
                ComponentInfo(
                    tag=text,
                    type=normalize_component_type(prefix),
                    family="",
                    description="",
                    position=pos,
                    terminals={},
                    attributes={"_source": "pdf_direct"},
                )
            )
        return components

    def _segments_to_wires(self, segments: list) -> list:
        """Wrap each WireSegment in a standalone WireInfo (no connectivity)."""
        from ..models import WireInfo  # noqa: PLC0415

        return [
            WireInfo(
                id=f"W{idx + 1}",
                wire_number="",
                from_endpoint=None,
                to_endpoint=None,
                segments=[seg],
            )
            for idx, seg in enumerate(segments)
        ]

    def _components_to_terminals(self, components: list) -> list:
        """Extract terminal-strip entries from components with X/XT prefix."""
        import re  # noqa: PLC0415

        from ..models import TerminalInfo  # noqa: PLC0415

        terminals: list[TerminalInfo] = []
        for comp in components:
            m = re.match(r"^([A-Z]{1,3})", comp.tag)
            prefix = m.group(1) if m else ""
            if prefix in ("X", "XT"):
                terminals.append(
                    TerminalInfo(strip=comp.tag, pin=comp.tag, description="", wire="")
                )
        return terminals

    def _merge_page(
        self, merged: SchematicData, page_data: SchematicData, page_num: int
    ) -> None:
        """Merge page_data into merged in-place, prefixing wire IDs."""
        merged.components.extend(page_data.components)
        merged.terminals.extend(page_data.terminals)
        merged.nets.extend(page_data.nets)

        for wire in page_data.wires:
            prefixed = WireInfo(
                id=f"{wire.id}_p{page_num}",
                wire_number=wire.wire_number,
                from_endpoint=wire.from_endpoint,
                to_endpoint=wire.to_endpoint,
                segments=wire.segments,
            )
            merged.wires.append(prefixed)
