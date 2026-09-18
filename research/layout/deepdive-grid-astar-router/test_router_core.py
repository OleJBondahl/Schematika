"""Synthetic regression checks for router_core.py's round-2 hardening.

Round 1's demo circuit had hand-picked, grid-aligned coordinates and never
exercised the off-grid-endpoint diagonal bug or the no-path fallback. These
are the checks that would have caught both before they showed up as
geometry-linter findings on the 98-component cabinet.

Run with: `uv run research/layout/deepdive-grid-astar-router/test_router_core.py`
"""

from router_core import (
    OrthogonalRouter,
    RouterConfig,
    RoutingError,
    rasterize_obstacles,
    route_pure,
)

from schematika.core.bbox import BoundingBox
from schematika.core.geometry import Point


def _is_orthogonal(points: list[Point]) -> bool:
    return all(
        abs(a.x - b.x) < 1e-9 or abs(a.y - b.y) < 1e-9
        for a, b in zip(points, points[1:], strict=False)
    )


def test_off_grid_endpoints_stay_orthogonal() -> None:
    # The exact shape of the real bug: an endpoint (142.68) that is not a
    # multiple of cell_size (5.0), routed to another off-grid endpoint far
    # enough away that the search takes multiple grid steps.
    cfg = RouterConfig()
    bounds = BoundingBox(min_x=-50.0, min_y=-50.0, max_x=200.0, max_y=200.0)
    start = Point(0.0, 145.0)
    end = Point(-10.0, 142.67949192431124)
    poly, _used = route_pure(
        start, end, blocked=set(), used_cells=frozenset(), bounds=bounds, config=cfg
    )
    assert poly[0] == start
    assert poly[-1] == end
    assert _is_orthogonal(poly), f"expected every segment axis-aligned, got {poly}"


def test_same_cell_off_axis_endpoints_get_a_corner() -> None:
    # Same-grid-cell start/end that don't share an axis -- the len(cells)<2
    # early-return path in _compress_to_turns, which used to skip
    # orthogonalization entirely.
    cfg = RouterConfig()
    bounds = BoundingBox(min_x=-50.0, min_y=-50.0, max_x=50.0, max_y=50.0)
    start = Point(0.0, 0.0)
    end = Point(1.5, 1.5)  # same 5mm cell as start, but diagonal from it
    poly, _used = route_pure(
        start, end, blocked=set(), used_cells=frozenset(), bounds=bounds, config=cfg
    )
    assert _is_orthogonal(poly), f"expected every segment axis-aligned, got {poly}"


def test_route_with_fallback_reports_and_stays_orthogonal() -> None:
    # A target completely walled in by obstacles: no A* path exists.
    cfg = RouterConfig(obstacle_clearance=0.0)
    wall = [
        BoundingBox(min_x=-100.0, min_y=-100.0, max_x=100.0, max_y=-5.0),
        BoundingBox(min_x=-100.0, min_y=5.0, max_x=100.0, max_y=100.0),
        BoundingBox(min_x=-100.0, min_y=-5.0, max_x=-5.0, max_y=5.0),
        BoundingBox(min_x=5.0, min_y=-5.0, max_x=100.0, max_y=5.0),
    ]
    bounds = BoundingBox(min_x=-100.0, min_y=-100.0, max_x=100.0, max_y=100.0)
    router = OrthogonalRouter(wall, bounds, cfg)
    start = Point(-50.0, 0.0)
    end = Point(0.0, 0.0)  # sealed inside the box formed by `wall`
    poly, used_fallback = router.route_with_fallback(start, end)
    assert used_fallback, "a fully walled-in target must trigger the fallback"
    assert poly[0] == start
    assert poly[-1] == end
    assert _is_orthogonal(poly)


def test_route_raises_when_no_fallback_requested() -> None:
    cfg = RouterConfig(obstacle_clearance=0.0)
    wall = [
        BoundingBox(min_x=-100.0, min_y=-100.0, max_x=100.0, max_y=-5.0),
        BoundingBox(min_x=-100.0, min_y=5.0, max_x=100.0, max_y=100.0),
        BoundingBox(min_x=-100.0, min_y=-5.0, max_x=-5.0, max_y=5.0),
        BoundingBox(min_x=5.0, min_y=-5.0, max_x=100.0, max_y=5.0),
    ]
    bounds = BoundingBox(min_x=-100.0, min_y=-100.0, max_x=100.0, max_y=100.0)
    router = OrthogonalRouter(wall, bounds, cfg)
    try:
        router.route(Point(-50.0, 0.0), Point(0.0, 0.0))
    except RoutingError:
        pass
    else:
        raise AssertionError("expected RoutingError from a fully walled-in target")


def test_pure_and_stateful_agree_on_a_fixed_obstacle_set() -> None:
    # The scenario OrthogonalRouter is actually a good fit for: one obstacle
    # set shared by every route (unlike large_cabinet.py's per-route
    # exclusion, see route_all.py's module docstring).
    cfg = RouterConfig()
    bounds = BoundingBox(min_x=-50.0, min_y=-50.0, max_x=150.0, max_y=150.0)
    obstacles = [BoundingBox(min_x=40.0, min_y=-10.0, max_x=60.0, max_y=60.0)]
    blocked = rasterize_obstacles(obstacles, cfg)

    pairs = [
        (Point(0.0, 0.0), Point(100.0, 0.0)),
        (Point(0.0, 20.0), Point(100.0, 20.0)),
    ]

    router = OrthogonalRouter(obstacles, bounds, cfg)
    stateful_polylines = [router.route(a, b) for a, b in pairs]

    used_cells: frozenset = frozenset()
    pure_polylines = []
    for a, b in pairs:
        poly, used_cells = route_pure(
            a, b, blocked=blocked, used_cells=used_cells, bounds=bounds, config=cfg
        )
        pure_polylines.append(poly)

    assert stateful_polylines == pure_polylines


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} synthetic checks passed")
