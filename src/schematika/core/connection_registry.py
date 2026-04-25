"""Connection registry for terminal-to-component wiring.

TerminalRegistry and Connection are domain-neutral data structures used
by GenerationState to track wiring connections during circuit generation.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Connection:
    """Represents a connection between a terminal pin and a component pin."""

    terminal_tag: str
    terminal_pin: str
    component_tag: str
    component_pin: str
    side: str  # 'top' or 'bottom'


@dataclass(frozen=True)
class TerminalRegistry:
    """Immutable registry for terminal connections."""

    connections: tuple[Connection, ...] = field(default_factory=tuple)

    def add_connection(
        self,
        terminal_tag: str,
        terminal_pin: str,
        component_tag: str,
        component_pin: str,
        side: str,
    ) -> "TerminalRegistry":
        """Returns a new TerminalRegistry with the added connection."""
        new_conn = Connection(
            terminal_tag, terminal_pin, component_tag, component_pin, side
        )
        return TerminalRegistry((*self.connections, new_conn))

    def add_connections(self, conns: list[Connection]) -> "TerminalRegistry":
        """Return a new ``TerminalRegistry`` with all *conns* appended."""
        return TerminalRegistry(self.connections + tuple(conns))
