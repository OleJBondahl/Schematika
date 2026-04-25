# Overview Module — Design Docs

Working notes for the planned `schematika.overview` module: an
auto-generated Graphviz system diagram showing the whole electrical system
at once for R&D context.

## Read in order

1. [`01-vision-and-scope.md`](01-vision-and-scope.md) — what we're building and why
2. [`02-data-sources.md`](02-data-sources.md) — what data exists in Schematika today and what's missing
3. [`03-consumer-pattern.md`](03-consumer-pattern.md) — how `auxillary_cabinet_v3` uses Schematika (the canonical consumer)
4. [`04-graphviz-reference.md`](04-graphviz-reference.md) — Graphviz mental model and pitfalls, distilled
5. [`05-overview-api.md`](05-overview-api.md) — proposed API shape and internal package layout
6. [`06-feedback-loop.md`](06-feedback-loop.md) — how AI agents iterate on the output without human review every cycle
7. [`07-open-questions.md`](07-open-questions.md) — items deliberately deferred or unresolved

## TL;DR

A new `src/schematika/overview/` package takes a built `Project` plus a
containment dict declared by the consumer, walks the existing `*BuildResult`
structures, and emits a single Graphviz SVG of the whole system. Pure-SVG
output, no HTML hyperlinks, no replacement for production drawings — this
is an R&D context view only.

The canonical consumer is one repo per physical system (template:
`auxillary_cabinet_v3`) containing the cabinet description, the PCBs that
sit inside it, and the cables out to field devices. Overview lives next to
the consumer's existing `cabinet.py` / `cables.py` entry points and is
called after `project.build_circuits()` has run.

## Source

Originating spec: [`R&D_overview.md`](../../R&D_overview.md) at the repo
root. These docs refine that spec with concrete data-model findings and
the recent design decisions (no hyperlinks, single-repo-per-system,
ignore the `block` module).
