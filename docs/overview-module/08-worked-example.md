# Worked End-to-End Example

A single concrete walk through one full Overview build, from consumer
script to validator output. Read this when implementing v0; it
anchors the abstract API in `05-overview-api.md` to a real artifact.

## Consumer file

`auxillary_cabinet_v3/src/overview.py` (new):

```python
"""Auxiliary Cabinet — system overview diagram."""

from cabinet import setup_project
from schematika import overview
from schematika.core.options import OverviewOptions
from schematika.overview import ContainerSpec


CONTAINMENT = {
    "cabinet_aux": ContainerSpec(
        label="Auxiliary Cabinet",
        kind="cabinet",
        circuits=(
            "power_switching",
            "psu",
            "distribution",
            "pumps",
            "pump_controll",
            "valve_control",
            "fans",
            "fan_controll",
            "pump_feedback",
            "fan_feedback",
            "plc_power",
        ),
    ),
    # Field devices land in the synthetic "<system>" container by
    # default. Override here once we want explicit "Field" grouping.
}


def main() -> None:
    project = setup_project()
    overview.build(
        project,
        options=OverviewOptions(
            containment=CONTAINMENT,
            output_path="src/system.svg",
        ),
    )


if __name__ == "__main__":
    main()
```

`overview.build()` auto-calls `project.build_circuits()` if
`project._results` is empty, so the consumer doesn't need to
orchestrate the build order.

## What gets emitted

Three files alongside `src/system.svg`:

- `src/system.svg` — the diagram, plain `-Tsvg` Graphviz output.
- `src/system.svg.expected.json` — emitter-written sidecar with
  canonical counts and structural summary; the validator's
  source-of-truth.
- `src/system.dot` — the raw DOT source. Useful for debugging layout
  issues.

### Sidecar shape

```json
{
  "version": 1,
  "graphviz_version": "12.1.2",
  "schematika_version": "0.1.7",
  "palette": {"power": "#c0392b", "signal": "#2980b9"},
  "counts": {"nodes": 47, "edges": 132, "clusters": 1},
  "containers": [
    {"id": "cabinet_aux", "label": "Auxiliary Cabinet",
     "parent": null, "child_units": ["X01", "X52", "Q1", ...]}
  ],
  "units": [
    {"id": "X52", "container": "cabinet_aux",
     "ports": ["1", "2", "3", "4", "5", "6", "7", "8"]},
    ...
  ],
  "edges": [
    {"src": "X52", "src_port": "3",
     "dst": "S3-CX", "dst_port": "3",
     "kind": "power", "color": "#c0392b"},
    ...
  ]
}
```

## Validator run

```
$ uv run python scripts/system_diagram_review.py src/system.svg
```

### Success path

```
[PASS palette]            132/132 edges in {power, signal}
[PASS edge_count]         132/132
[PASS node_count]         47/47
[PASS cluster_count]      1/1
[PASS cluster_contains]   all child units inside their cluster bbox
[PASS page_size]          1404 x 992 ≤ 4000 x 4000
RESULT: PASS
SVG:    src/system.svg
PNG:    src/system.png  (sha256 7f3c...)
```

Exit code `0`.

### Failure path — agent deleted nodes to "fix" overlap

```
[PASS palette]            128/128 edges in {power, signal}
[FAIL edge_count]         128/132   (4 missing)
[FAIL node_count]         44/47     (3 missing)
[PASS cluster_count]      1/1
RESULT: FAIL  (counts disagree with sidecar)
SVG:    src/system.svg
PNG:    src/system.png  (sha256 1a8e...)
```

Exit code `2`. The agent's report template requires quoting these
lines verbatim, so "looks fine" claims that omit a missing-count line
are caught at review time.

### Failure path — Graphviz layout regression

```
[PASS palette]            132/132 edges in {power, signal}
[PASS edge_count]         132/132
[PASS node_count]         47/47
[PASS cluster_count]      1/1
[FAIL cluster_contains]   unit "X52" bbox extends 12px below cluster
                          "cabinet_aux" bbox
RESULT: FAIL  (cluster containment violated)
```

Exit code `2`. Real cause: a Graphviz patch upgrade nudged a layout.
Either pin the version or accept the new layout and regenerate the
structural snapshot.

## Going wrong, going right

| Symptom | Where to look |
|---|---|
| "Cluster has 0 children" | Containment dict references a circuit key not in `project._results`. Check spelling |
| "Cycle in containment graph" | A `parent` chain loops back. Validator prints the cycle path |
| `OverviewExtractionError: _results not a dict` | `Project` internal storage shape changed. Update `overview/extractor.py` adapter |
| All edges colored as "signal" | Default classifier didn't match anything as power. Pass a custom `signal_kind` callable, or rename signals to match the default patterns |
| SVG renders, validator fails on `[FAIL ortho]` | `splines` set on a subgraph instead of root; or compass points missing |
| Cluster has no fill | `style=rounded` without `filled`. Use `style="rounded,filled"; fillcolor="..."` |
| `dot: syntax error` | Unescaped `&` / `<` / `>` in port names or HTML labels. Or a port name colliding with a DOT keyword |
| Validator class-name parsing breaks | Someone passed `format='svg:cairo'`. Use plain `format='svg'` |

## Iteration loop

```
1. Edit src/schematika/overview/{model,extractor,emitter,validate}.py
2. cd ../auxillary_cabinet_v3
3. uv run python src/overview.py            # writes system.svg + sidecar
4. uv run python scripts/system_diagram_review.py src/system.svg
5. Read system.png (and crops, when v0.5+ adds them)
6. If FAIL: fix, repeat. If PASS: done
```

This is the same loop as `scripts/pid_review.py` for P&ID, with one
new artifact (the sidecar) and one new exit-code meaning (`3` for
snapshot diff once tier 3 ships).
