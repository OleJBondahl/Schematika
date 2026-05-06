"""Typst PDF compiler. Requires the optional `typst` package."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from schematika.electrical.system.system import render_system
from schematika.rendering.typst.frame_generator import (
    A3_HEIGHT,
    CONTENT_HEIGHT,
    CONTENT_WIDTH,
    INNER_FRAME_Y1,
    INNER_FRAME_Y2,
    generate_frame,
)
from schematika.rendering.typst.markdown_converter import markdown_to_typst


@dataclass
class TypstCompilerConfig:
    """Configuration for the Typst PDF compiler."""

    drawing_name: str = ""
    drawing_number: str = ""
    author: str = ""
    project: str = ""
    revision: str = "00"
    logo_path: str | None = None
    font_family: str = "Times New Roman"
    root_dir: str = "."
    temp_dir: str = "temp"
    datetime_stamp: bool = True


@dataclass
class _Page:
    """Internal representation of a page in the document."""

    page_type: str  # "schematic", "front", "plc_report", "terminal_report", "custom", "cable", "cable_toc"
    title: str = ""
    svg_path: str = ""
    terminals_csv_path: str = ""
    csv_path: str = ""
    md_path: str = ""
    notice: str | None = None
    typst_content: str = ""
    terminal_titles: dict[str, str] | None = None
    cable_svg_paths: list[tuple[str, str, str, str]] | None = None
    cable_toc_entries: list[tuple[str, str]] | None = None


class TypstCompiler:
    """Multi-page Typst PDF compiler."""

    def __init__(self, config: TypstCompilerConfig) -> None:
        """Build a ``TypstCompiler`` using the given *config*."""
        self.config = config
        self._pages: list[_Page] = []

    def add_schematic_page(
        self,
        title: str,
        svg_path: str,
        terminals_csv_path: str | None = None,
    ) -> None:
        """Add a schematic page with optional terminal table."""
        self._pages.append(
            _Page(
                page_type="schematic",
                title=title,
                svg_path=svg_path,
                terminals_csv_path=terminals_csv_path or "",
            )
        )

    def add_front_page(
        self,
        md_path: str,
        notice: str | None = None,
    ) -> None:
        """Add a front page from a Markdown file."""
        self._pages.append(_Page(page_type="front", md_path=md_path, notice=notice))

    def add_plc_report(self, csv_path: str) -> None:
        """Add a PLC connections report page."""
        self._pages.append(_Page(page_type="plc_report", csv_path=csv_path))

    def add_terminal_report(
        self,
        csv_path: str,
        terminal_titles: dict[str, str],
    ) -> None:
        """Add a system terminal report page."""
        self._pages.append(
            _Page(
                page_type="terminal_report",
                csv_path=csv_path,
                terminal_titles=terminal_titles,
            )
        )

    def add_custom_page(self, title: str, typst_content: str) -> None:
        """Add a page with raw Typst content."""
        self._pages.append(
            _Page(page_type="custom", title=title, typst_content=typst_content)
        )

    def add_cable_pages(self, cables: list[tuple[str, str, str, str]]) -> None:
        """Each tuple: (svg_path, designator, title, length_str)."""
        self._pages.append(_Page(page_type="cable", cable_svg_paths=cables))

    def add_cable_toc(self, entries: list[tuple[str, str]]) -> None:
        """Two-column TOC; each entry is `(designator, title)`."""
        self._pages.append(_Page(page_type="cable_toc", cable_toc_entries=entries))

    def compile(self, output_path: str) -> None:
        """Raises ImportError when the optional `typst` package is missing."""
        try:
            import typst as typst_mod
        except ImportError as err:
            msg = (
                "The 'typst' package is required for PDF compilation. "
                "Install it with: pip install schematika[pdf]"
            )
            raise ImportError(msg) from err

        config = self.config
        temp_dir = str(Path(config.root_dir) / config.temp_dir)
        Path(temp_dir).mkdir(parents=True, exist_ok=True)

        # Generate A3 frame SVG
        frame_svg_path = str(Path(temp_dir) / "A3_frame.svg")
        frame_circuit = generate_frame(font_family=config.font_family)
        render_system(frame_circuit, frame_svg_path, width="420mm", height="297mm")

        # Resolve template path
        template_path = self._get_template_path()

        # Copy template to temp dir so Typst can find it
        template_dest = str(Path(temp_dir) / "a3_drawing.typ")
        with Path(template_path).open(encoding="utf-8") as f:
            template_content = f.read()
        with Path(template_dest).open("w", encoding="utf-8") as f:
            f.write(template_content)

        # Build Typst document
        content = self._build_typst_content(frame_svg_path, template_dest)

        # Compile
        typst_mod.compile(
            content.encode("utf-8"),
            output=output_path,
            root=config.root_dir,
        )

    def _get_template_path(self) -> str:
        """Resolve the path to the a3_drawing.typ template."""
        here = str(Path(__file__).resolve().parent)
        return str(Path(here) / "templates" / "a3_drawing.typ")

    def _build_typst_content(self, frame_svg_path: str, template_path: str) -> str:
        """Assemble the full Typst document string."""
        config = self.config

        # Template and main content paths are relative to root_dir
        template_rel = os.path.relpath(template_path, config.root_dir).replace(
            "\\", "/"
        )

        # Template-internal paths (frame, logo) must be relative to
        # the template's own directory, because Typst resolves image()
        # paths relative to the file they appear in.
        template_dir = str(Path(template_path).resolve().parent)

        frame_svg_rel_to_template = os.path.relpath(
            str(Path(frame_svg_path).resolve()), template_dir
        ).replace("\\", "/")

        # Logo path handling (also relative to template dir)
        logo_arg = "none"
        if config.logo_path:
            logo_rel = os.path.relpath(
                str(Path(config.logo_path).resolve()), template_dir
            ).replace("\\", "/")
            logo_arg = f'"{logo_rel}"'

        # Calculate positioning constants from frame geometry
        clip_width = CONTENT_WIDTH - 2  # 398mm
        clip_height = CONTENT_HEIGHT - 2  # 275mm
        title_offset_from_bottom = (A3_HEIGHT - INNER_FRAME_Y2) + 5  # 15mm

        date_line = "" if config.datetime_stamp else "\n#set document(date: none)\n"

        content = f"""
#import "{template_rel}": a3_drawing
{date_line}
#let circuit_scale = 100%
#let clip_width = {clip_width}mm
#let clip_height = {clip_height}mm
#let schematic_left = 15mm
#let schematic_top = {INNER_FRAME_Y1}mm
#let title_offset = {title_offset_from_bottom}mm
#let terminal_top = 15mm
#let terminal_right = 14mm

// Helper: read CSV and create a terminal table
#let terminal_table(csv_path) = {{
    let data = csv(csv_path)
    table(
      columns: (60pt, 150pt),
      align: (left, left),
      fill: (x, y) => if y == 0 {{ gray.lighten(50%) }} else {{ none }},
      inset: 5pt,
      ..data.flatten()
    )
}}

// Helper: place schematic SVG with title and optional terminal table
#let schematic(path, title: none, terminals_csv: none) = {{
  place(top + left, dx: schematic_left, dy: schematic_top)[
    #block(width: clip_width, height: clip_height, clip: true)[
      #scale(circuit_scale, origin: top + left)[
        #image(path)
      ]
    ]
  ]

  place(bottom + center, dy: -title_offset)[
    #if title != none [
      #text(size: 18pt, weight: "bold")[#title]
    ]
  ]

  if terminals_csv != none {{
      place(top + right, dx: -terminal_right, dy: terminal_top)[
          #terminal_table(terminals_csv)
      ]
  }}
}}

// Apply document template
#show: a3_drawing.with(
  drawing_number: "{config.drawing_number}",
  drawing_name: "{config.drawing_name}",
  author: "{config.author}",
  project: "{config.project}",
  revision: "{config.revision}",
  frame_path: "{frame_svg_rel_to_template}",
  logo_path: {logo_arg},
  font_family: "{config.font_family}",
)
"""

        # Append pages (skip trailing pagebreak on the last page)
        last_idx = len(self._pages) - 1
        for i, page in enumerate(self._pages):
            page_content = self._render_page(page)
            if i == last_idx:
                page_content = page_content.replace("#pagebreak()\n", "")
            content += page_content

        return content

    def _render_page(self, page: _Page) -> str:
        """Render a single page to Typst markup."""
        result: str
        match page.page_type:
            case "schematic":
                result = self._render_schematic_page(page)
            case "front":
                result = self._render_front_page(page)
            case "plc_report":
                result = self._render_plc_report(page)
            case "terminal_report":
                result = self._render_terminal_report(page)
            case "custom":
                result = self._render_custom_page(page)
            case "cable":
                result = self._render_cable_pages(page)
            case "cable_toc":
                result = self._render_cable_toc(page)
            case _:
                assert_never(page.page_type)  # ty: ignore[type-assertion-failure]
        return result

    def _render_schematic_page(self, page: _Page) -> str:
        """Render a schematic page with SVG and optional terminal table."""
        svg_rel = self._rel_path(page.svg_path)
        result = f"\n// Page: {page.title}\n"

        if page.terminals_csv_path:
            csv_rel = self._rel_path(page.terminals_csv_path)
            result += (
                f'#schematic("{svg_rel}", '
                f'title: "{page.title}", '
                f'terminals_csv: "{csv_rel}")\n'
            )
        else:
            result += f'#schematic("{svg_rel}", title: "{page.title}")\n'

        result += "#pagebreak()\n"
        return result

    def _render_front_page(self, page: _Page) -> str:
        """Render a front page from Markdown."""
        return markdown_to_typst(page.md_path, notice=page.notice)

    def _render_plc_report(self, page: _Page) -> str:
        """Render the PLC connections report page."""
        csv_rel = self._rel_path(page.csv_path)
        return _PLC_REPORT_TYPST.replace("__CSV_PATH__", csv_rel)

    def _render_terminal_report(self, page: _Page) -> str:
        """Render the system terminal report page."""
        csv_rel = self._rel_path(page.csv_path)
        titles = page.terminal_titles or {}

        # Serialize titles to Typst map
        title_items = []
        for tag, title in titles.items():
            safe_title = title.replace('"', '\\"')
            title_items.append(f'"{tag}": "{safe_title}"')

        typst_title_map = "#let terminal_titles = (\n" + ",\n".join(title_items) + "\n)"

        return _TERMINAL_REPORT_TYPST.replace("__TITLE_MAP__", typst_title_map).replace(
            "__CSV_PATH__", csv_rel
        )

    def _render_custom_page(self, page: _Page) -> str:
        """Render a custom Typst content page."""
        result = ""
        if page.title:
            result += f"\n// Custom Page: {page.title}\n"
        result += page.typst_content
        result += "\n#pagebreak(weak: true)\n"
        return result

    def _render_cable_pages(self, page: _Page) -> str:
        """Render cable drawings in a flowing two-column layout."""
        cables = page.cable_svg_paths or []
        if not cables:
            return ""

        result = "\n// Cable Drawings\n"
        result += "#pad(left: 15mm, right: 15mm, top: 15mm, bottom: 20mm)[\n"
        result += "  #columns(2, gutter: 24mm)[\n"

        for svg_path, designator, title, length_str in cables:
            svg_rel = self._rel_path(svg_path)
            safe_title = title.replace('"', '\\"')
            length_text = f"Length: {length_str}" if length_str else "Length:"
            # Label for TOC page-number lookup (sanitize designator for label)
            label = designator.replace("-", "").replace(" ", "")
            result += "    #block(breakable: false, width: 100%)[\n"
            result += f"      === {designator} #h(0.5em) {safe_title} <{label}>\n"
            result += f"      #align(left)[{length_text}]\n"
            result += f'      #image("{svg_rel}")\n'
            result += "      #v(4mm)\n"
            result += "    ]\n"

        result += "  ]\n"
        result += "]\n"
        result += "#pagebreak()\n"
        return result

    def _render_cable_toc(self, page: _Page) -> str:
        """Render a three-column cable table of contents with page numbers."""
        entries = page.cable_toc_entries or []
        if not entries:
            return ""

        result = "\n// Cable Table of Contents\n"
        result += "#place(bottom + center, dy: -title_offset)[\n"
        result += '  #text(size: 18pt, weight: "bold")[Table of Contents]\n'
        result += "]\n"
        result += "#pad(left: 25mm, right: 25mm, top: 40mm, bottom: 40mm)[\n"
        result += "#context [\n"
        result += "  #columns(3, gutter: 3em)[\n"
        result += "    #table(\n"
        result += "      columns: (auto, 1fr, auto),\n"
        result += "      align: (left, left, right),\n"
        result += "      inset: 5pt,\n"
        result += "      stroke: 0.25pt + gray,\n"
        result += "      table.header(\n"
        result += '        text(size: 10pt, weight: "bold")[Cable],\n'
        result += '        text(size: 10pt, weight: "bold")[Description],\n'
        result += '        text(size: 10pt, weight: "bold")[Page],\n'
        result += "      ),\n"

        for designator, title in entries:
            safe_title = title.replace('"', '\\"')
            label = designator.replace("-", "").replace(" ", "")
            result += f'      text(size: 9pt, weight: "bold")[{designator}],\n'
            result += f"      text(size: 9pt)[{safe_title}],\n"
            result += f"      text(size: 9pt)[#{{ let loc = query(<{label}>).first().location(); counter(page).at(loc).first() }}],\n"

        result += "    )\n"
        result += "  ]\n"
        result += "]\n"
        result += "]\n"
        result += "#pagebreak()\n"
        return result

    def _rel_path(self, path: str) -> str:
        """Convert an absolute or relative path to a Typst-friendly relative path."""
        if Path(path).is_absolute():
            path = os.path.relpath(path, self.config.root_dir)
        return path.replace("\\", "/")


# ---------------------------------------------------------------------------
# Inline Typst templates for reports
# ---------------------------------------------------------------------------

_PLC_REPORT_TYPST = r"""
// PLC Connections Report
#place(bottom + center, dy: -title_offset)[
  #text(size: 18pt, weight: "bold")[PLC I/O Connections]
]
#pad(left: 25mm, right: 25mm, top: 40mm, bottom: 40mm)[

#let plc_report(csv_path) = {
    let data = csv(csv_path)
    let rows = data.slice(1)

    // Group by Module designation (col 0), keep MPN (col 1)
    let groups = (:)
    let mpns = (:)

    for row in rows {
        let mod = row.at(0)
        let current = groups.at(mod, default: ())
        current.push(row)
        groups.insert(mod, current)
        if row.at(1) != "" { mpns.insert(mod, row.at(1)) }
    }

    columns(3, gutter: 5em)[
        #for (mod, group_rows) in groups.pairs() [
             #block(breakable: true)[
                 #let mpn = mpns.at(mod, default: "")
                 #table(
                    columns: (0.4fr, 0.5fr, 0.6fr),
                    align: (center, left, left),
                    fill: (x, y) => if y == 1 { gray.lighten(85%) } else { none },
                    inset: 4pt,
                    stroke: 0.25pt + gray,
                    table.header(
                        table.cell(colspan: 3, fill: none, stroke: none, inset: (left: 0pt, bottom: 2pt, top: 0pt, right: 0pt))[
                            #text(weight: "bold", size: 12pt, fill: blue.darken(30%))[#mod]
                            #h(0.5em)
                            #text(size: 10pt, fill: gray.darken(20%))[#mpn]
                        ],
                        text(size: 9pt, weight: "bold")[PLC Pin],
                        text(size: 9pt, weight: "bold")[Terminal],
                        text(size: 9pt, weight: "bold")[Component],
                    ),
                    ..group_rows.map(r => (
                        text(size: 9pt, weight: "bold")[#r.at(2)],
                        text(size: 9pt)[#r.at(5)],
                        text(size: 9pt)[#r.at(3):#r.at(4)]
                    )).flatten()
                 )
                 #v(1em)
             ]
        ]
    ]
}

#plc_report("__CSV_PATH__")

] // end pad

#pagebreak()
"""

_TERMINAL_REPORT_TYPST = r"""
// System Terminal Report
#place(bottom + center, dy: -title_offset)[
  #text(size: 18pt, weight: "bold")[System Terminal Report]
]
#pad(left: 25mm, right: 25mm, top: 40mm, bottom: 40mm)[
__TITLE_MAP__

#let terminal_report(csv_path) = {
    let data = csv(csv_path)
    if data.len() < 2 { return }
    let header = data.at(0)
    let rows = data.slice(1)

    // Group by Terminal Tag (index 2)
    let groups = (:)

    for row in rows {
        let tag = row.at(2)
        let current = groups.at(tag, default: ())
        current.push(row)
        groups.insert(tag, current)
    }

    // Helper to get bridge indicator for a row
    let get_bridge_indicator(row_idx, bridge_groups) = {
        if bridge_groups == none { return none }

        for (group_idx, group) in bridge_groups.enumerate() {
            if row_idx in group {
                let pos_in_group = group.position(i => i == row_idx)
                let group_size = group.len()

                let colors = (blue.darken(20%), green.darken(20%), orange.darken(20%), purple.darken(20%))
                let color = colors.at(calc.rem(group_idx, colors.len()))

                if group_size <= 1 {
                    return none
                } else if pos_in_group == 0 {
                    return (text(fill: color, weight: "bold")[┌], color)
                } else if pos_in_group == group_size - 1 {
                    return (text(fill: color, weight: "bold")[└], color)
                } else {
                    return (text(fill: color, weight: "bold")[│], color)
                }
            }
        }
        return none
    }

    columns(3, gutter: 5em)[
        #let keys = groups.keys().sorted()
        #for tag in keys [
             #let group_rows = groups.at(tag)
             #block(breakable: true)[
                 #let description = terminal_titles.at(tag, default: "")
                 #{
                     let bridge_groups = ()
                     let bridge_map = (:)

                     for (idx, row) in group_rows.enumerate() {
                         if row.len() > 6 {
                             let b_id = row.at(6)
                             if b_id != "" {
                                 let current_group = bridge_map.at(b_id, default: ())
                                 current_group.push(idx)
                                 bridge_map.insert(b_id, current_group)
                             }
                         }
                     }
                     bridge_groups = bridge_map.values()

                     table(
                        columns: (0.35fr, 0.35fr, 0.35fr, 0.35fr, 0.35fr, 0.15fr),
                        align: (left, center, center, left, center, center),
                        fill: (x, y) => if y == 1 { gray.lighten(85%) } else { none },
                        inset: 3pt,
                        stroke: 0.25pt + gray,
                        table.header(
                            table.cell(colspan: 6, fill: none, stroke: none, inset: (left: 0pt, bottom: 2pt, top: 0pt, right: 0pt))[
                                #text(weight: "bold", size: 12pt, fill: blue.darken(30%))[#tag - #description]
                            ],
                            text(size: 9pt, weight: "bold")[From],
                            text(size: 9pt, weight: "bold")[Pin],
                            text(size: 9pt, weight: "bold")[#tag],
                            text(size: 9pt, weight: "bold")[To],
                            text(size: 9pt, weight: "bold")[Pin],
                            text(size: 9pt, weight: "bold")[Bridge],
                        ),
                        ..group_rows.enumerate().map(((idx, r)) => {
                            let bridge = get_bridge_indicator(idx, bridge_groups)
                            (
                                text(size: 9pt)[#r.at(0)],
                                text(size: 9pt)[#r.at(1)],
                                text(size: 9pt, weight: "bold")[#r.at(3)],
                                text(size: 9pt)[#r.at(4)],
                                text(size: 9pt)[#r.at(5)],
                                if bridge != none { bridge.at(0) } else { [] }
                            )
                        }).flatten()
                     )
                 }
                 #v(1em)
             ]
        ]
    ]
}

#terminal_report("__CSV_PATH__")

] // end pad

#pagebreak()
"""
