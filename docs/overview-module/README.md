# Overview Module — Design Docs

Working notes for the planned `schematika.overview` module: an
auto-generated Graphviz system diagram showing the whole electrical system
at once for R&D context.

## Read in order

1. [`01-vision-and-scope.md`](01-vision-and-scope.md) — what we're building and why
2. [`02-data-sources.md`](02-data-sources.md) — what data exists in Schematika today and what's missing
3. [`03-consumer-pattern.md`](03-consumer-pattern.md) — how `auxillary_cabinet_v3` uses Schematika (the canonical consumer)
4. [`04-graphviz-reference.md`](04-graphviz-reference.md) — Graphviz mental model and pitfalls, distilled
5. [`05-overview-api.md`](05-overview-api.md) — proposed API shape, package layer, internal layout
6. [`06-feedback-loop.md`](06-feedback-loop.md) — how AI agents iterate without human review every cycle
7. [`07-open-questions.md`](07-open-questions.md) — resolved decisions and items deliberately deferred
8. [`08-worked-example.md`](08-worked-example.md) — full end-to-end example: consumer file, sidecar, validator output

## TL;DR

A new `src/schematika/overview/` package takes a built `Project` plus a
containment dict declared by the consumer, walks the existing
`*BuildResult` structures, and emits a single Graphviz SVG of the whole
system. Pure-SVG output, no HTML hyperlinks. v0 ships with two signal
kinds (`power`, `signal`); the palette grows on demand. Color-coded
edges, ortho routing, HTML-table multi-port nodes, nested clusters for
containment.

The canonical consumer is one repo per physical system (template:
`auxillary_cabinet_v3`) containing the cabinet description, the PCBs
that sit inside it, and the cables out to field devices. Overview is a
new domain package (sibling of `electrical/`, `pcb/`, `cable/`,
`pid/`) — not part of `core/`, since it shells out to `dot`. It lives
next to the consumer's existing `cabinet.py` / `cables.py` entry
points and auto-calls `project.build_circuits()` if results are empty.

## Source

Originating spec: [`R&D_overview.md`](../../R&D_overview.md) at the repo
root. These docs refine that spec with concrete data-model findings and
the recent design decisions (no hyperlinks, single-repo-per-system,
ignore the `block` module).
