"""Schematika MCP server — 5 tools for AI circuit generation."""

from __future__ import annotations

import difflib
import inspect
import signal
import tempfile
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, Never

from mcp.server.fastmcp import FastMCP  # ty: ignore[unresolved-import]

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType, ModuleType

mcp = FastMCP("schematika")

# ---------------------------------------------------------------------------
# Symbol catalog — built once at import time
# ---------------------------------------------------------------------------

_SYMBOL_NAMES: list[str] = [
    "no_contact",
    "nc_contact",
    "spdt_contact",
    "coil",
    "breaker",
    "thermal_overload",
    "fuse",
    "motor",
    "contactor",
    "estop",
    "turn_switch",
    "estop_button",
    "turn_actuator",
    "terminal",
    "psu",
    "block",
    "terminal_box",
    "ref",
    "ct",
    "ct_assembly",
]


def _get_symbols_module() -> ModuleType:
    from schematika.electrical import symbols

    return symbols


def _get_symbol_func(name: str) -> Callable[..., Any] | None:
    mod = _get_symbols_module()
    return getattr(mod, name, None)


def _pin_default_for(name: str) -> str:
    """Extract the default pins value from a symbol function's signature."""
    func = _get_symbol_func(name)
    if func is None:
        return "n/a"
    sig = inspect.signature(func)
    for param_name in ("pins", "contact_pins", "coil_pins"):
        if param_name in sig.parameters:
            default = sig.parameters[param_name].default
            if default is inspect.Parameter.empty:
                continue
            if default is None:
                return "None (auto-selected based on poles)"
            return repr(default)
    return "(none)"


def _short_description(name: str) -> str:
    """First line of docstring, or empty string."""
    func = _get_symbol_func(name)
    if func is None or not func.__doc__:
        return ""
    first_line = func.__doc__.strip().split("\n")[0].strip()
    # Remove trailing period for table consistency
    return first_line.rstrip(".")


# ---------------------------------------------------------------------------
# Tool 1: list_symbols
# ---------------------------------------------------------------------------


@mcp.tool()
def list_symbols() -> str:
    """List all available symbol factory functions with default pins and descriptions.

    Returns a formatted table of every IEC 60617 symbol in schematika.
    Use this to discover which symbols are available before generating code.
    """
    lines = [
        "| Factory Function | Default Pins | Description |",
        "|---|---|---|",
    ]
    for name in _SYMBOL_NAMES:
        pins = _pin_default_for(name)
        desc = _short_description(name)
        lines.append(f"| `{name}` | {pins} | {desc} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 2: describe_symbol
# ---------------------------------------------------------------------------


@mcp.tool()
def describe_symbol(name: str) -> str:
    """Get detailed info for one symbol: docstring, default pins, and usage example.

    Args:
        name: The symbol factory function name (e.g. 'breaker').
    """
    func = _get_symbol_func(name)
    if func is None:
        suggestions = difflib.get_close_matches(name, _SYMBOL_NAMES, n=5, cutoff=0.4)
        msg = f"Symbol '{name}' not found."
        if suggestions:
            msg += f" Did you mean: {', '.join(suggestions)}?"
        return msg

    parts: list[str] = [f"## {name}\n"]

    # Docstring
    doc = inspect.getdoc(func) or "(no docstring)"
    parts.append(doc)
    parts.append("")

    # Signature
    sig = inspect.signature(func)
    parts.append(f"**Signature:** `{name}{sig}`")
    parts.append("")

    # Default pins
    pins_repr = _pin_default_for(name)
    parts.append(f"**Default pins:** {pins_repr}")
    parts.append("")

    # Usage example
    parts.append("**Usage example:**")
    parts.append("```python")
    parts.append("from schematika import CircuitBuilder, create_initial_state")
    parts.append(f"from schematika import {name}")
    parts.append("")
    parts.append("state = create_initial_state()")
    parts.append("b = CircuitBuilder(state)")
    parts.append("b.set_layout(x=0, y=0, spacing=150)")
    parts.append(f'b.add_symbol({name}, tag_prefix="X", poles=1)')
    parts.append('result = b.build(count=1, wire_labels=["L1"])')
    parts.append("```")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Tool 3: validate_circuit
# ---------------------------------------------------------------------------

_EXEC_TIMEOUT_SECONDS = 5


def _make_exec_globals() -> dict:
    """Build a restricted globals dict with schematika pre-imported."""
    from schematika import electrical
    from schematika.electrical import symbols

    g: dict = {"__builtins__": __builtins__}
    # Import everything from the electrical public API
    for attr in electrical.__all__:
        g[attr] = getattr(electrical, attr)
    # Also make all symbols directly available
    for sym_name in _SYMBOL_NAMES:
        fn = getattr(symbols, sym_name, None)
        if fn is not None:
            g[sym_name] = fn
    return g


class _TimeoutError(Exception):
    pass


def _timeout_handler(signum: int, frame: FrameType | None) -> Never:
    msg = "Execution timed out"
    raise _TimeoutError(msg)


# POSIX-only signal primitives. Bound via getattr so ty narrows `is not None`
# rather than failing to narrow `hasattr(signal, ...)` / `sys.platform` checks.
_SIGALRM = getattr(signal, "SIGALRM", None)
_alarm = getattr(signal, "alarm", None)


def _exec_code(code: str) -> dict:
    """Execute user code in a controlled namespace. Returns the namespace."""
    g = _make_exec_globals()
    # Try to set a timeout (Unix only; on Windows this is a no-op)
    if _SIGALRM is not None and _alarm is not None:
        old_handler = signal.signal(_SIGALRM, _timeout_handler)
        _alarm(_EXEC_TIMEOUT_SECONDS)
    try:
        exec(code, g)
    finally:
        if _SIGALRM is not None and _alarm is not None:
            _alarm(0)
            signal.signal(_SIGALRM, old_handler)
    return g


@mcp.tool()
def validate_circuit(code: str) -> str:
    """Parse and execute Python circuit code to check for errors.

    Runs the code in a sandboxed namespace with all schematika imports
    pre-loaded. Returns 'OK' if the code executes without errors, or a
    structured error report with the exception type, message, and
    suggestions for fixing common mistakes.

    Args:
        code: Python source code that uses the schematika API.
    """
    try:
        _exec_code(code)
    except _TimeoutError:
        return (
            "ERROR: Execution timed out "
            f"(>{_EXEC_TIMEOUT_SECONDS}s). "
            "Simplify the circuit or check for infinite loops."
        )
    except SyntaxError as e:
        return (
            f"SYNTAX ERROR at line {e.lineno}:\n"
            f"  {e.text}\n"
            f"  {e.msg}\n\n"
            "Fix the Python syntax and try again."
        )
    except Exception as e:
        tb = traceback.format_exc()
        error_type = type(e).__name__
        error_msg = str(e)

        result = f"ERROR ({error_type}):\n{error_msg}\n"

        # Add targeted suggestions for schematika-specific exceptions
        if error_type == "PortNotFoundError":
            result += (
                "\nSuggestion: The error message above lists "
                "the available ports. Use one of those port names."
            )
        elif error_type == "TagReuseError":
            result += (
                "\nSuggestion: This tag is already in use. "
                "Use a different tag_prefix or pass reuse_tags "
                "to builder.build()."
            )
        elif error_type == "WireLabelMismatchError":
            result += (
                "\nSuggestion: The wire_labels list length must "
                "equal the number of vertical wires (= max poles "
                "across components)."
            )
        elif error_type == "TerminalReuseError":
            result += (
                "\nSuggestion: Terminal numbers must be unique. "
                "Check your terminal pin assignments."
            )

        result += f"\n--- Full traceback ---\n{tb}"
        return result
    else:
        return "OK — code executed without errors."


# ---------------------------------------------------------------------------
# Tool 4: render_circuit
# ---------------------------------------------------------------------------


@mcp.tool()
def render_circuit(code: str, format: str = "svg") -> str:
    """Execute circuit code and render the output to a file.

    The code must call render_system() to produce output. The rendered
    file is saved to a temporary directory and its path is returned.

    Args:
        code: Python source code that calls render_system().
        format: Output format — currently only 'svg' is supported.
    """
    if format not in ("svg",):
        return f"ERROR: Unsupported format '{format}'. Supported: svg"

    tmp_dir = tempfile.mkdtemp(prefix="schematika_mcp_")

    try:
        g = _make_exec_globals()

        # Patch render_system to redirect output into our temp dir
        original_render = g.get("render_system")
        rendered_files: list[str] = []

        def patched_render(
            circuits: object,
            filename: str,
            **kwargs: Any,  # noqa: ANN401
        ) -> object:
            actual_path = str(Path(tmp_dir) / Path(filename).name)
            rendered_files.append(actual_path)
            # original_render is typed `object | None` because g.get returns
            # object; in practice it is always the render_system callable
            # populated by _make_exec_globals(). See SUPPRESSIONS.md (Wave T2).
            return original_render(circuits, actual_path, **kwargs)  # ty: ignore[call-non-callable]

        g["render_system"] = patched_render

        if _SIGALRM is not None and _alarm is not None:
            old_handler = signal.signal(_SIGALRM, _timeout_handler)
            _alarm(_EXEC_TIMEOUT_SECONDS)
        try:
            exec(code, g)
        finally:
            if _SIGALRM is not None and _alarm is not None:
                _alarm(0)
                signal.signal(_SIGALRM, old_handler)

    except _TimeoutError:
        return f"ERROR: Execution timed out (>{_EXEC_TIMEOUT_SECONDS}s)."
    except Exception as e:
        tb = traceback.format_exc()
        return f"ERROR ({type(e).__name__}):\n{e}\n\n{tb}"
    else:
        if rendered_files:
            return f"OK — rendered to: {rendered_files[0]}"
        return (
            f"WARNING: Code executed without errors but render_system() "
            f"was not called. No output file was produced.\n"
            f"Temp directory: {tmp_dir}"
        )


# ---------------------------------------------------------------------------
# Tool 5: get_reference
# ---------------------------------------------------------------------------

_REFERENCE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "docs" / "LLM_REFERENCE.md"
)


def _load_reference() -> str:
    if _REFERENCE_PATH.is_file():
        return _REFERENCE_PATH.read_text(encoding="utf-8")
    return ""


def _parse_sections(text: str) -> dict[str, str]:
    """Split markdown into sections keyed by header text (lowercase)."""
    sections: dict[str, str] = {}
    current_header = ""
    current_lines: list[str] = []

    for line in text.split("\n"):
        if line.startswith("## "):
            if current_header:
                sections[current_header] = "\n".join(current_lines).strip()
            current_header = line.lstrip("#").strip().lower()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_header:
        sections[current_header] = "\n".join(current_lines).strip()

    return sections


@mcp.tool()
def get_reference(topic: str = "") -> str:
    """Return relevant sections from the LLM reference documentation.

    Pass a keyword to search for a specific topic (e.g. 'pins', 'state',
    'mistakes', 'symbols', 'tags'). Pass an empty string or 'all' to
    return the full document.

    Args:
        topic: A keyword to filter sections, or 'all'/empty for everything.
    """
    text = _load_reference()
    if not text:
        return "ERROR: LLM_REFERENCE.md not found. Expected at: " + str(_REFERENCE_PATH)

    topic = topic.strip().lower()
    if not topic or topic == "all":
        return text

    sections = _parse_sections(text)

    # Find sections whose header contains the topic keyword
    # Also try singular/plural variations
    topic_variants = {topic}
    if topic.endswith("s"):
        topic_variants.add(topic[:-1])
    else:
        topic_variants.add(topic + "s")

    matches = []
    for header, content in sections.items():
        if any(v in header for v in topic_variants):
            matches.append(content)

    if matches:
        return "\n\n---\n\n".join(matches)

    # Fallback: search full text for lines containing the topic
    matching_lines = [line for line in text.split("\n") if topic in line.lower()]

    if matching_lines:
        return (
            f"No section header matched '{topic}', "
            f"but found {len(matching_lines)} matching lines:\n\n"
            + "\n".join(matching_lines)
        )

    return (
        f"No results found for topic '{topic}'. "
        "Try: pins, state, symbols, tags, mistakes"
    )
