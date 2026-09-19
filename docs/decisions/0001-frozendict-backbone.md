# 0001. The backbone data structure is a strict, immutable nested `frozendict` model

**Status:** Accepted, 2026-09-19 (sole author)
**Scope:** the internal data structure that every input feeds and every output reads, for the planned rewrite.

## Decision

Schematika's backbone model is a **strict, immutable, nested-mapping ("dict in dict") data structure built on Python 3.15's built-in `frozendict`** ([PEP 814](https://peps.python.org/pep-0814/)). We design it ourselves and keep full control over how data is stored, validated, merged and read.

It is **not** built on a graph library or a database. networkx, SQL engines and RDF may still appear later as *projections* built from the model on demand, never as the place the data lives.

Schematika is being **rewritten to a new structure**. Today's structure (the `catalog/` identity types, the `*BuildResult` types, `Project`) is being replaced, not migrated to or from, and it is not a constraint on the new design. It serves as reference material for requirements only.

## What is decided, and what is not

Decided:

- The truth is a nested immutable mapping, owned by Schematika.
- The language floor moves to Python 3.15 (see Consequences).

Not decided (next session): the shape of the nesting, how records are represented, the schema and validation mechanism, the static-typing story, indexes, merge and edit semantics, identity and canonical form. See "Open design questions".

## Context

Two studies were run on 2026-09-19 (benchmark of seven backends, prototypes, source reading). Findings that shaped this decision:

- **Speed and memory do not decide it.** At 10k ports (a large cabinet) every backend answered in under 60 ms. The owner also stated that memory and speed are irrelevant for this application.
- **networkx as the store works** behind a typed facade (a prototype reproduced the own-structure prototype's results, with an identical content digest), but it fails silently in ways this project has been fighting: `nx.Graph` merges parallel wires into one edge; `add_edge` to an unknown id creates a phantom node; `nx.compose` lets the second input win on an id clash; `nx.freeze` still allows attribute writes. It ships no type information.
- **Ladybug (embedded graph DB, 0.20.4)** enforces more: primary-key uniqueness, relation endpoint types, multiplicity, no delete-with-edges, loud query typos, rollback. It still coerces property types silently, silently ignores an edge to a missing id, lacks `NOT NULL`/`UNIQUE`/`CHECK`, and returns untyped dicts. It is pre-1.0 and its PyPI metadata says `requires_python <3.15`, which conflicts with this decision.
- **The domain rules that matter are ours to write under any store:** a device's pins match its catalog part, declared nets agree with physical conductors, hierarchies are trees, merging inputs never clashes on an id.

Prototype code and benchmark output from the studies are **not** in the repo (they lived in a temporary session scratchpad). The findings above are the record.

## What `frozendict` gives, and its limits

Facts from PEP 814, and checked by running Python 3.15.0a8 (an alpha; the final release may differ):

- Immutable mapping; **hashable when all keys and values are hashable**; hash ignores order. A frozen dataclass with a `frozendict` field is hashable.
- Not a `dict` subclass; item assignment raises `TypeError`; `fd | {...}` returns a new instance.
- `json.dumps(frozendict(...))` worked on 3.15.0a8.
- **Shallow only.** A plain `dict` or `list` stored inside is still mutable through the outer `frozendict` (verified). Deep immutability must be enforced by us at construction.
- **Copy on modification, no structural sharing.** Changing a nested value rebuilds every level on the path to the root.

## Consequences

- **`requires-python` moves from `>=3.14` to `>=3.15`.** Python 3.15.0 final is scheduled for 2026-10-01 ([PEP 790](https://peps.python.org/pep-0790/)); until then only pre-releases exist. This decision does **not** change `pyproject.toml`; the bump is its own step.
- **Toolchain must be checked for 3.15 before the bump.** `pyproject.toml` already pins ruff `target-version` to `py313` because of a formatter bug, and `ty`, `deal`, `import-linter`, `pytest` and other tools need to support 3.15.
- **Ladybug cannot be used, even as an optional projection,** until it supports 3.15. Other optional projections (rustworkx, duckdb, pyoxigraph) need 3.15 wheels, which are unchecked. networkx is pure Python but unverified on 3.15.
- **We own everything a library would have given:** identity, canonical serialisation and digest, indexes, merge guards, validation, typing. No library provides these for us.
- The core can stay dependency-free (`frozendict` is a builtin). The invariants and conventions in `CLAUDE.md` describe today's structure and are revisited by the rewrite, including invariant 5 (frozen dataclasses by default).

## Requirements carried forward

These come from the studies. Treat them as requirements and hypotheses, not settled design.

- Stable opaque entity ids, separate from mutable designations (`-K1`, `J1`). Deterministic ids from the authoring path, never from auto-numbered refs (SKiDL refs shift when a part is inserted).
- A **Function** layer between item and port (EPLAN: one physical device has several functions, drawn as separate symbols on separate pages), and **three hierarchies** over the same objects per IEC 81346: function (`=`), product (`-`), location (`+`).
- Keep the declared **Net** (intent, N-ary) and the physical **Conductor** (realisation, two-ended) as separate facts, with a validator that compares them.
- Provenance on every fact (which input line created it), so errors name a source, not an internal id.
- Presentation and layout live outside the model, keyed by entity id. Derived facts are recomputed, never written back into the asserted model.
- Every output is a pure function of the model. Canonical, diffable serialisation for golden tests. Merging inputs must refuse id clashes.

## Open design questions (for the design session)

1. **Shape of the nesting:** for example kind, then id, then record; how relations (net membership, conductors, hierarchy) are represented inside it.
2. **Record representation:** nested `frozendict` all the way down, or frozen dataclasses holding `frozendict` fields, or both.
3. **Schema enforcement:** validate and deep-freeze at the builder-to-frozen boundary; which leaf types are allowed (scalars, tuples, `frozendict`); rejecting mutable values that would leak through the shallow freeze.
4. **Static typing:** how `ty` sees `frozendict[str, ...]`, and whether a typed schema (a `TypedDict`-like or dataclass layer) is possible over it. Untested.
5. **Indexes:** whether they are part of the model or derived and cached from it; how they are rebuilt after an edit.
6. **Edit and merge semantics:** path-copy updates, merging inputs with clash refusal, diff by entity hash.
7. **Identity and canonical form:** id derivation, ordering, content digest, serialisation format and `schema_version`.
8. **Builder API:** the mutable authoring layer that freezes into the model, and how today's chain/rung and `route()`/`field_devices()` front ends lower into it.
9. **Projections:** how networkx and SQL views are produced from the model, given the Python 3.15 wheel situation.
10. **Moving over from today's code:** none of today's types constrain the new structure. Open: how the two consumer projects are moved to the rewrite, and whether today's outputs serve as a regression oracle for the new pipeline.
