"""Regression test for Project._render_multi_circuit_pages's Windows path-length bug.

Joining every circuit key on a merged multi-circuit page (`"_".join(keys)`)
can exceed Windows' ~260-char path limit once a page merges several
descriptively-named circuits, failing `ElementTree.write` with a bare
`FileNotFoundError` nowhere near the real cause. `_safe_merged_key` falls
back to a short hash once the joined key gets long.
"""

from schematika.project import _MAX_MERGED_KEY_LEN, _safe_merged_key


def test_short_joined_key_is_unchanged() -> None:
    keys = ["loop_1_start", "loop_1_coil"]
    assert _safe_merged_key(keys) == "loop_1_start_loop_1_coil"


def test_long_joined_key_is_hashed_and_short() -> None:
    keys = [f"descriptive_circuit_key_number_{i:03d}" for i in range(10)]
    joined = "_".join(keys)
    assert len(joined) > _MAX_MERGED_KEY_LEN

    safe = _safe_merged_key(keys)
    assert len(safe) <= _MAX_MERGED_KEY_LEN
    assert safe.startswith(keys[0])


def test_long_joined_key_is_deterministic() -> None:
    keys = [f"circuit_{i:03d}_" + "x" * 20 for i in range(8)]
    assert _safe_merged_key(keys) == _safe_merged_key(keys)


def test_different_long_keys_do_not_collide() -> None:
    keys_a = [f"circuit_a_{i:03d}_" + "x" * 20 for i in range(8)]
    keys_b = [f"circuit_b_{i:03d}_" + "x" * 20 for i in range(8)]
    assert _safe_merged_key(keys_a) != _safe_merged_key(keys_b)
