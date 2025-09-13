from simple_calculator import add


def test_add_ints():
    assert add(1, 2) == 3


def test_add_floats():
    assert add(1.5, 2.5) == 4.0
