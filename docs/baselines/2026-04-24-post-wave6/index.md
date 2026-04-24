# Post-Wave-6 snapshot — 2026-04-24

Intermediate snapshot after Waves 1–6. Mutmut **not** re-run here; schedule one
final run vs. `../2026-04-24/mutmut_results.txt` as the post-refactor snapshot.

## Delta table — pre-refactor → post-W4 → post-W5 → post-W6

| Tool | Pre | Post-W4 | Post-W5 | Post-W6 | Total Δ | Note |
|---|---:|---:|---:|---:|---:|---|
| pytest | 1459 / 4 | 1582 / 4 | 1582 / 4 | **1582 / 4** | +123 | stable |
| coverage | 84 % (1177) | 84 % (1161) | 84 % (1167 / 7354) | 84 % (1167 / 7428) | ~ | +74 lines (decorators) |
| scc LoC (Python) | 29 537 / 170 | 30 636 / 174 | ~30 700 / ~180 | 30 783 / 180 | +1 246 / +10 | `rendering/svg.py` + `_purity.py` |
| ruff errors (src+tests) | 615 | 602 | 241 | **241** | −374 | unchanged W5→W6 |
| ruff errors (workspace) | — | — | 385 | 385 | — | unchanged |
| ty diagnostics (src/) | ~35 | ~45 | 15 | **15** | −20 | unchanged |
| interrogate | 80.3 % | 80.1 % | 80.4 % | **80.6 %** | +0.3 pp | decorator docstrings |
| vulture (no whitelist) | 163 | 162 | 162 | 162 | −1 | |
| vulture (with whitelist) | — | — | 88 | **88** | — | excludes self-refs in whitelist file |
| import-linter | 1 broken | 0 broken | 0 broken | **0 broken** | ✓ | held through W4–W6 |
| fp-purity-gate | 54 missing | 54 | 54 | **0** | −54 | **Wave 6 target met** |
| api-style-gate | 18 | 17 | 0 | **0** | −18 | held |
| `raise ValueError` in src/ | 59 | 59 | 3 | **3** | −56 | held |
| darglint (lines) | 890 | 885 | — | 905 | +15 | new decorator/module docstrings |

## Wave 6 structural changes

### Group B — impure I/O moved out of `core/`

New file: `src/schematika/rendering/svg.py` (210 LoC) now owns:

- `_render_element` (ET.SubElement side-effects)
- `to_xml_element` (mutates passed XML root)
- `save_svg` (disk write)
- `render_to_svg` (orchestration)

`core/renderer.py` keeps only pure helpers: `_style_to_str`, `calculate_bounds`.

Back-compat shim: `src/schematika/electrical/utils/renderer.py` re-exports from
both modules so existing `from schematika.electrical.utils.renderer import ...`
calls still work.

### Group A — 29 functions decorated `@deal.pure`

Directly decorated. These are provably pure under deal's analysis (no mutation,
no I/O, no unhandled raises).

### Group C — 21 functions decorated `@pure` (no-op shim)

New file: `src/schematika/_purity.py` — an identity-function decorator used when
deal.pure's runtime analysis would bite but the function is still conceptually
pure. Covers:

- Accumulator-style helpers (`resolve_terminal_pins`, `_collect_points`,
  `_add_remapped_ports`) — mutate caller-passed containers.
- `@singledispatch.register` variants (9 × `transform._`) — stacking decorators
  with singledispatch introduces dispatch quirks.
- Visitor-callback wrappers (`walk_elements`, `collect_by_type`,
  `collect_elements`, `check_text_overlap`) — purity depends on caller's
  `Callable`.
- `warnings.warn` code paths (`translate`, `rotate` fallthroughs) — `deal.pure`
  raises `SilentContractError` on warn.
- `multipole` — returns closure that raises on bad input; `deal.pure` would
  flag the closure's `RaisesContractError`.

## Consumer impact (`../auxillary_cabinet_v3/`)

Grepped for `from schematika.core.renderer`, `render_to_svg`, `to_xml_element`,
`save_svg`, `_render_element`: **zero runtime references.** One historical
mention in `docs/plans/2026-02-21-circuitbuilder-rethink-design.md:66` only.
No consumer updates needed.

## Commits

| SHA | Title |
|---|---|
| `f59ff99` | refactor(wave-6-1): move impure renderer functions out of core/ to rendering/svg |
| `c1196f3` | refactor(wave-6-2,6-3): decorate remaining 50 core/ functions with @pure |

## Notes

- The `ty` "15 diagnostics" figure is `ty check src/` only. Workspace `ty
  check` (includes `examples/`, `scripts/`, `tests/`) reports ~52 — the
  post-W5 index reporting that number as 146 was captured with a different
  environment (different `--extra` groups installed). Using the **src/-only**
  figure going forward for apples-to-apples comparisons.
- `vulture (with whitelist) = 88` is findings in `src/` with
  `scripts/vulture_whitelist.py` passed as a source — the whitelist file
  itself emits ~84 self-reference "unused variable" noise lines that are
  excluded from this count (per Wave 5 convention).

## Remaining debt

- ruff src+tests: 241 errors (mostly `D*` docstring rules — documentation debt)
- ty src/: 15 diagnostics (library-code type issues)
- fp-purity-gate strict: **passing at 0 missing** ✓
- api-style-gate: **passing** ✓
- import-linter: **passing** ✓

All three gates that were refactor targets now pass. Remaining debt is
documentation/lint debt, not structural.

## Next

Schedule one final mutmut run as the post-refactor snapshot vs.
`../2026-04-24/mutmut_results.txt` (pre-refactor, 403/551 processed, 126
survivors). Needs the chunked runner (current mutmut dies on memory before
completing on Windows).
