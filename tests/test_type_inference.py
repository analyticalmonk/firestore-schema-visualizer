from datetime import datetime
from unittest.mock import MagicMock
from utils import infer_field_type, merge_field_types


def test_infer_string():
    assert infer_field_type("hello") == "string"


def test_infer_int():
    assert infer_field_type(42) == "number"


def test_infer_float():
    assert infer_field_type(3.14) == "number"


def test_infer_bool():
    assert infer_field_type(True) == "boolean"


def test_infer_timestamp():
    assert infer_field_type(datetime.now()) == "timestamp"


def test_infer_list():
    assert infer_field_type([1, 2, 3]) == "array"


def test_infer_dict():
    assert infer_field_type({"a": 1}) == "map"


def test_infer_none():
    assert infer_field_type(None) == "null"


def test_infer_reference():
    ref = MagicMock()
    ref.__class__.__name__ = "DocumentReference"
    assert infer_field_type(ref) == "reference"


def test_infer_geopoint():
    geo = MagicMock()
    geo.__class__.__name__ = "GeoPoint"
    assert infer_field_type(geo) == "geopoint"


def test_infer_unknown_type():
    obj = MagicMock()
    obj.__class__.__name__ = "SomeWeirdType"
    assert infer_field_type(obj) == "unknown"


def test_merge_picks_most_common():
    counts = {"string": 5, "number": 2, "null": 3}
    assert merge_field_types(counts) == "string"


def test_merge_ignores_null_when_others_exist():
    counts = {"null": 10, "string": 1}
    assert merge_field_types(counts) == "string"


def test_merge_null_only():
    counts = {"null": 5}
    assert merge_field_types(counts) == "null"


def test_merge_empty():
    assert merge_field_types({}) == "unknown"
