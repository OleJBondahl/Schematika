from schematika.electrical.model.core import Point, Port, Vector
from schematika.electrical.model.parts import (
    box,
    create_pin_labels,
    standard_text,
    terminal_circle,
)
from schematika.electrical.model.primitives import Circle, Polygon


class TestPartsUnit:
    def test_standard_text(self):
        t = standard_text("K1", Point(0, 0))
        assert t.content == "K1"
        assert t.position.x < 0  # It applies an offset to the left
        assert t.anchor == "end"

    def test_terminal_circle(self):
        c = terminal_circle(Point(10, 10), filled=True)
        assert isinstance(c, Circle)
        assert c.center == Point(10, 10)
        assert c.style.fill == "black"

        c2 = terminal_circle(Point(10, 10), filled=False)
        assert isinstance(c2, Circle)
        assert c2.style.fill == "none"

    def test_box(self):
        b = box(Point(0, 0), 10, 20)
        assert isinstance(b, Polygon)
        assert len(b.points) == 4
        # check dimensions roughly
        xs = [p.x for p in b.points]
        ys = [p.y for p in b.points]
        assert max(xs) - min(xs) == 10
        assert max(ys) - min(ys) == 20

    def test_create_pin_labels(self):
        # Setup ports
        ports = {
            "1": Port("1", Point(0, 0), Vector(0, -1)),  # UP
            "2": Port("2", Point(0, 10), Vector(0, 1)),  # DOWN
        }
        labels = create_pin_labels(ports, ("13", "14"))
        assert len(labels) == 2
        assert labels[0].content == "13"
        assert labels[0].position.x < 0
        assert labels[1].position.x < 0

    def test_create_pin_labels_preserves_insertion_order(self):
        """Pin labels should follow port insertion order, not alphabetical order."""
        # Create ports in a specific non-alphabetical order
        # With current implementation (sorted keys), "A1" comes before "L" and "N"
        # We want order "L", "A1", "N"

        # Note: We must ensure the dict preserves order (Python 3.7+)
        ports = {}
        ports["L"] = Port("L", Point(0, 0), Vector(0, -1))
        ports["A1"] = Port("A1", Point(10, 0), Vector(0, -1))
        ports["N"] = Port("N", Point(20, 0), Vector(0, -1))

        labels = create_pin_labels(ports, ("LIVE", "AUX", "NEUTRAL"))

        # labels[0] is "LIVE". Should be at Port "L" (x=0)
        # labels[1] is "AUX". Should be at Port "A1" (x=10)
        # labels[2] is "NEUTRAL". Should be at Port "N" (x=20)

        # We check relative X positions.
        # LIVE should be leftmost (0), AUX middle (10), NEUTRAL rightmost (20).
        # But if sorted: A1 (10) gets LIVE, L (0) gets AUX.
        # So LIVE would be at 10, AUX at 0.

        # Check X positions (ignoring small offsets)
        x_live = labels[0].position.x
        x_aux = labels[1].position.x

        # If correct: x_live < x_aux (0 < 10)
        # If bug: x_live > x_aux (10 > 0)
        assert x_live < x_aux, (
            f"Expected LIVE (at L) to be left of AUX (at A1). "
            f"Got x_live={x_live}, x_aux={x_aux}"
        )
