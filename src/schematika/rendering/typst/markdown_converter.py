"""Simple Markdown to Typst converter for front pages.

Supports headings (# ## ###), tables (| col | col |), and paragraphs.
"""

from pathlib import Path


def markdown_to_typst(
    md_path: str,
    width: str = "50%",
    notice: str | None = None,
) -> str:
    """Convert a Markdown file to Typst markup for a front page.

    Supports:
    - Headings (``#``, ``##``, ``###``)
    - Simple Markdown tables (``| col1 | col2 |``)
    - Plain text paragraphs

    Args:
        md_path: Path to the Markdown file.
        width: Width constraint for the content block (e.g. "50%").
        notice: Optional notice text placed at the bottom of the page.
            If None, no notice is added.

    Returns:
        Typst markup string for the front page (including a trailing pagebreak).
    """
    try:
        with Path(md_path).open(encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return ""

    typst_lines, extracted_notice = _convert_lines(lines, width)

    effective_notice = notice if notice is not None else extracted_notice
    if effective_notice:
        typst_lines.append(_notice_block(effective_notice, width))

    typst_lines.append("#pagebreak()")
    return "\n".join(typst_lines)


def _convert_lines(lines: list[str], width: str) -> tuple[list[str], str | None]:
    """Convert markdown lines to Typst markup.

    Returns a tuple of (typst_lines, extracted_notice). If the markdown
    contains a ``## Notice`` section, its body text is extracted and
    returned separately (not rendered inline).
    """
    typst_lines = []
    typst_lines.append(r"#align(center + horizon)[")
    typst_lines.append(f"  #block(width: {width})[")

    in_table = False
    table_rows: list[str] = []
    in_notice = False
    notice_parts: list[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            if in_table:
                typst_lines.extend(_flush_table(table_rows))
                in_table = False
                table_rows = []
            continue

        if line.startswith("# "):
            typst_lines.append(f"    = {line[2:]}")
            typst_lines.append(r"    #v(1em)")
        elif line.lower() == "## notice":
            in_notice = True
        elif line.startswith("## "):
            in_notice = False
            typst_lines.append(f"    == {line[3:]}")
            typst_lines.append(r"    #v(0.5em)")
        elif in_notice:
            notice_parts.append(line)
        elif line.startswith("### "):
            typst_lines.append(f"    === {line[4:]}")
            typst_lines.append(r"    #v(0.5em)")
        elif line.startswith("|"):
            if "---" in line:
                continue  # Skip table separator rows
            in_table = True
            table_rows.append(line)
        else:
            typst_lines.append(f"    {line}")
            typst_lines.append(r"    #parbreak()")

    if in_table:
        typst_lines.extend(_flush_table(table_rows))

    typst_lines.append(r"  ]")
    typst_lines.append(r"]")

    extracted_notice = " ".join(notice_parts) if notice_parts else None
    return typst_lines, extracted_notice


def _flush_table(rows: list[str]) -> list[str]:
    """Convert accumulated Markdown table rows to a Typst table."""
    if not rows:
        return []

    # Determine column count from first row
    first_cols = [c.strip() for c in rows[0].split("|") if c.strip()]
    num_cols = max(len(first_cols), 1)

    result = []
    result.append(f"    #table(columns: {num_cols}, stroke: 0.5pt, inset: 5pt,")
    col_aligns = ", ".join(["left"] * num_cols)
    result.append(f"      align: ({col_aligns}),")

    for row in rows:
        cols = [c.strip() for c in row.split("|") if c.strip()]
        result.extend(f"      [{col}]," for col in cols)

    result.append("    )")
    return result


def _notice_block(notice: str, width: str) -> str:
    """Generate a Typst notice block placed at the bottom of the page."""
    return f"""
#place(
  bottom + center,
  dy: -40mm,
  float: false,
  block(
    width: {width},
    fill: luma(240),
    inset: 12pt,
    radius: 4pt,
    stroke: 1pt + luma(150),
    text(size: 9pt, style: "italic")[
      {notice}
    ]
  )
)
"""
