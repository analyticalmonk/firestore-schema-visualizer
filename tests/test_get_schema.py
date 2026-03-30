from unittest.mock import MagicMock
from utils import get_schema


def _make_doc(doc_id, data, subcollections=None):
    """Helper to create a mock Firestore document."""
    doc = MagicMock()
    doc.id = doc_id
    doc.to_dict.return_value = data
    doc.reference = MagicMock()
    if subcollections:
        sub_cols = []
        for name, docs in subcollections.items():
            col = MagicMock()
            col.id = name
            col.limit.return_value.stream.return_value = docs
            sub_cols.append(col)
        doc.reference.collections.return_value = sub_cols
    else:
        doc.reference.collections.return_value = []
    return doc


def _make_collection(name, docs):
    """Helper to create a mock Firestore collection."""
    col = MagicMock()
    col.id = name
    col.limit.return_value.stream.return_value = docs
    return col


def test_basic_typed_schema():
    doc = _make_doc("u1", {"name": "Alice", "age": 30, "active": True})
    col = _make_collection("users", [doc])
    db = MagicMock()
    db.collections.return_value = [col]

    schema, refs = get_schema(db)
    assert schema["users"] == {"name": "string", "age": "number", "active": "boolean"}
    assert refs == {}


def test_reference_field_tracked():
    ref_mock = MagicMock()
    ref_mock.__class__.__name__ = "DocumentReference"
    ref_mock.parent = MagicMock()
    ref_mock.parent.id = "teams"

    doc = _make_doc("u1", {"name": "Alice", "team_ref": ref_mock})
    col = _make_collection("users", [doc])
    db = MagicMock()
    db.collections.return_value = [col]

    schema, refs = get_schema(db)
    assert schema["users"]["team_ref"] == "reference"
    assert refs == {"users": [("team_ref", "teams")]}


def test_subcollection_discovery():
    sub_doc = _make_doc("p1", {"title": "Post", "likes": 5})
    parent_doc = _make_doc("u1", {"name": "Alice"}, subcollections={"posts": [sub_doc]})
    col = _make_collection("users", [parent_doc])
    db = MagicMock()
    db.collections.return_value = [col]

    schema, refs = get_schema(db)
    assert "users" in schema
    assert "users.posts" in schema
    assert schema["users.posts"] == {"title": "string", "likes": "number"}


def test_max_depth_limits_recursion():
    deep_doc = _make_doc("d1", {"val": "deep"})
    mid_doc = _make_doc("m1", {"val": "mid"}, subcollections={"deep": [deep_doc]})
    top_doc = _make_doc("t1", {"val": "top"}, subcollections={"mid": [mid_doc]})
    col = _make_collection("top", [top_doc])
    db = MagicMock()
    db.collections.return_value = [col]

    schema, refs = get_schema(db, max_depth=1)
    assert "top" in schema
    assert "top.mid" in schema
    assert "top.mid.deep" not in schema


def test_type_merge_across_docs():
    doc1 = _make_doc("u1", {"score": 10})
    doc2 = _make_doc("u2", {"score": None})
    doc3 = _make_doc("u3", {"score": 20})
    col = _make_collection("users", [doc1, doc2, doc3])
    db = MagicMock()
    db.collections.return_value = [col]

    schema, refs = get_schema(db)
    assert schema["users"]["score"] == "number"  # number wins over null


def test_empty_collection():
    col = _make_collection("empty", [])
    db = MagicMock()
    db.collections.return_value = [col]
    schema, refs = get_schema(db)
    assert schema["empty"] == {}
    assert refs == {}


def test_doc_with_none_to_dict():
    doc = _make_doc("u1", None)
    col = _make_collection("users", [doc])
    db = MagicMock()
    db.collections.return_value = [col]
    schema, refs = get_schema(db)
    assert schema["users"] == {}
