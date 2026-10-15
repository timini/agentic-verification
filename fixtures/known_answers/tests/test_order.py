"""Known answer: an order-dependent pair. Passes in file order, fails when the order changes."""

STATE: list[int] = []


def test_first_appends():
    STATE.append(1)
    assert STATE == [1]


def test_second_needs_first():
    assert STATE == [1]
