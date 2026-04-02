# Typed Schema Extraction + Subcollection Discovery - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance `get_schema` to infer field types and recursively discover subcollections, then update all downstream consumers.

**Architecture:** A new `infer_field_type(value)` helper maps Python/Firestore values to type labels. `get_schema` is rewritten to return `dict[str, dict[str, str]]` and recurse into subcollections using dot-notation keys. Reference-type fields are pre-populated as known relationships before the LLM runs. All diagram generators are updated for typed fields and subcollection visualization.

**Tech Stack:** Python, firebase-admin SDK, openai, pydot, plantuml, pytest

---

### Task 1: Add type inference helpers + tests

**Files:**
- Create: `tests/test_type_inference.py`
- Modify: `utils.py:1-11` (add imports, new functions before `get_schema`)

**Step 1: Write the failing tests**

Create `tests/test_type_inference.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_type_inference.py -v`
Expected: ImportError - `infer_field_type` and `merge_field_types` do not exist yet

**Step 3: Implement the helpers in utils.py**

Add these two functions at the top of `utils.py`, after the imports:

```python
def infer_field_type(value):
    """Map a Python/Firestore value to a type label string."""
    if value is None:
        return "null"
    if isinstance(value, bool):  # must be before int check since bool is subclass of int
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, datetime):
        return "timestamp"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "map"
    class_name = value.__class__.__name__
    if class_name == "DocumentReference":
        return "reference"
    if class_name == "GeoPoint":
        return "geopoint"
    return "unknown"


def merge_field_types(type_counts):
    """Given a dict of {type_label: count}, return the most common non-null type."""
    if not type_counts:
        return "unknown"
    non_null = {t: c for t, c in type_counts.items() if t != "null"}
    if non_null:
        return max(non_null, key=non_null.get)
    return "null"
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_type_inference.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/test_type_inference.py utils.py
git commit -m "feat: add type inference helpers with tests"
```

---

### Task 2: Rewrite get_schema with type inference + subcollection discovery

**Files:**
- Modify: `utils.py:13-35` (`get_schema` function)
- Create: `tests/test_get_schema.py`

**Step 1: Write the failing tests**

Create `tests/test_get_schema.py`:

```python
from unittest.mock import MagicMock, patch
from datetime import datetime
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
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_get_schema.py -v`
Expected: FAIL - `get_schema` returns old format (list, not dict), no `refs` return value

**Step 3: Rewrite get_schema**

Replace the existing `get_schema` function in `utils.py`:

```python
def get_schema(db, max_depth=3, sample_size=50):
    """
    Retrieve the schema of a Firestore database with inferred field types
    and recursive subcollection discovery.

    Args:
        db: The Firestore database client.
        max_depth: Maximum subcollection nesting depth to explore (default 3).
        sample_size: Number of documents to sample per collection (default 50).

    Returns:
        A tuple of (schema, reference_fields):
        - schema: dict[str, dict[str, str]] - collection path -> {field_name: type_label}
        - reference_fields: dict[str, list[tuple[str, str]]] - collection path -> [(field, target_collection)]
    """
    schema = {}
    reference_fields = {}

    def _process_collection(collection_ref, path_prefix, depth):
        col_path = f"{path_prefix}.{collection_ref.id}" if path_prefix else collection_ref.id
        field_type_counts = {}  # {field_name: {type_label: count}}
        seen_subcollections = set()

        docs = collection_ref.limit(sample_size).stream()
        for doc in docs:
            doc_data = doc.to_dict()
            for field, value in doc_data.items():
                if field not in field_type_counts:
                    field_type_counts[field] = {}
                type_label = infer_field_type(value)
                field_type_counts[field][type_label] = field_type_counts[field].get(type_label, 0) + 1

                # Track reference targets
                if type_label == "reference" and hasattr(value, "parent"):
                    target = value.parent.id
                    if col_path not in reference_fields:
                        reference_fields[col_path] = []
                    pair = (field, target)
                    if pair not in reference_fields[col_path]:
                        reference_fields[col_path].append(pair)

            # Discover subcollections
            if depth < max_depth:
                for sub_col in doc.reference.collections():
                    if sub_col.id not in seen_subcollections:
                        seen_subcollections.add(sub_col.id)
                        _process_collection(sub_col, col_path, depth + 1)

        # Merge type counts into final types
        schema[col_path] = {
            field: merge_field_types(counts)
            for field, counts in field_type_counts.items()
        }

    for collection in db.collections():
        _process_collection(collection, "", 0)

    return schema, reference_fields
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_get_schema.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add utils.py tests/test_get_schema.py
git commit -m "feat: rewrite get_schema with type inference and subcollection discovery"
```

---

### Task 3: Update identify_relationships_llm

**Files:**
- Modify: `utils.py:38-94` (`identify_relationships_llm` function)

**Step 1: Update the function**

Replace `identify_relationships_llm` to accept the new schema format and pre-populated references:

```python
def identify_relationships_llm(schema, known_references=None):
    """
    Identify foreign key relationships using LLM, supplemented by known reference fields.

    Args:
        schema: dict[str, dict[str, str]] - collection path -> {field: type}
        known_references: dict[str, list[tuple[str, str]]] - pre-identified reference relationships

    Returns:
        dict[str, list[tuple[str, str]]] - collection -> [(field, related_collection)]
    """
    if known_references is None:
        known_references = {}

    relationships = {}
    schema_context = json.dumps(schema, indent=2)
    collection_names = list(schema.keys())

    for collection, fields in schema.items():
        print(f"Collection: {collection}\n")
        relationships[collection] = []

        # Pre-populate known reference relationships
        if collection in known_references:
            relationships[collection].extend(known_references[collection])
            print(f"  Known references: {known_references[collection]}")

        # Filter out fields already identified as references
        known_field_names = {f for f, _ in relationships[collection]}
        remaining_fields = {f: t for f, t in fields.items() if f not in known_field_names}

        if not remaining_fields:
            print("  All fields resolved via references, skipping LLM.\n")
            continue

        prompt = (
            f"Given the following Firestore schema (collection -> field: type):\n\n{schema_context}\n\n"
            f"The available collections are: {collection_names}\n\n"
            f"For the collection '{collection}', examine these fields: {json.dumps(remaining_fields)}\n\n"
            f"Identify any fields that likely represent foreign key relationships to other collections. "
            f"Only identify relationships to collections that exist in the schema above. "
            f"Respond with a JSON object mapping field names to their related collection, "
            f'e.g. {{"user_id": "users"}}. If no relationships found, respond with {{}}.'
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            response_format={"type": "json_object"}
        )
        result_text = response.choices[0].message.content.strip()
        print(f"  LLM result: {result_text}")

        llm_relationships = json.loads(result_text)
        for field, target in llm_relationships.items():
            if target in schema:
                relationships[collection].append((field, target))

        print()

    return relationships
```

Key changes:
- Accepts `known_references` from `get_schema` reference tracking
- Uses `response_format={"type": "json_object"}` instead of a second LLM call to parse
- Removes the `i += 1` bug
- Validates that LLM-suggested targets actually exist in the schema

**Step 2: Verify no import changes needed**

The function uses `json` and `client` which are already imported/defined.

**Step 3: Commit**

```bash
git add utils.py
git commit -m "feat: update identify_relationships_llm for typed schema, single LLM call"
```

---

### Task 4: Update create_schema_graph_llm

**Files:**
- Modify: `utils.py:97-149` (`create_schema_graph_llm` function)

**Step 1: Update the function**

```python
def create_schema_graph_llm(schema, relationships):
    """
    Create a pydot directed graph visualizing the Firestore schema.

    Nodes show collection name with typed fields. Edges show FK relationships
    and subcollection parent-child links.

    Args:
        schema: dict[str, dict[str, str]] - collection path -> {field: type}
        relationships: dict[str, list[tuple[str, str]]] - collection -> [(field, related_collection)]

    Returns:
        str: The output filename of the generated PNG.
    """
    graph = pydot.Dot(graph_type='digraph', rankdir='LR')
    graph.set_node_defaults(shape='record')

    for collection, fields in schema.items():
        field_lines = [f"{name} : {ftype}" for name, ftype in fields.items()]
        label = "{" + collection + "|" + "\\l".join(field_lines) + "\\l}"
        node = pydot.Node(collection, label=label)
        graph.add_node(node)

    # Add subcollection parent-child edges
    for collection in schema:
        if "." in collection:
            parent = collection.rsplit(".", 1)[0]
            if parent in schema:
                edge = pydot.Edge(parent, collection, label="subcollection", style="dashed")
                graph.add_edge(edge)

    # Add FK relationship edges
    for collection, rels in relationships.items():
        for field, related_collection in rels:
            edge = pydot.Edge(collection, related_collection.strip(), label=field.strip())
            graph.add_edge(edge)

    output_file = f'firestore_schema_llm_{datetime.now().strftime("%Y%m%d%H%M%S")}.png'
    graph.write_png(output_file)
    return output_file
```

**Step 2: Commit**

```bash
git add utils.py
git commit -m "feat: update pydot graph for typed fields and subcollections"
```

---

### Task 5: Update generate_plantuml_text

**Files:**
- Modify: `utils.py:151-217` (`generate_plantuml_text` and `generate_uml_diagram`)

**Step 1: Update generate_plantuml_text**

```python
def generate_plantuml_text(schema, relationships, generate_diagram=False, output_file=None):
    """
    Generate PlantUML text for Firestore collections with typed fields.

    Args:
        schema: dict[str, dict[str, str]] - collection path -> {field: type}
        relationships: dict[str, list[tuple[str, str]]] - collection -> [(field, related_collection)]
        generate_diagram: Whether to render a PNG diagram. Default False.
        output_file: Output PNG path. Required if generate_diagram is True.

    Returns:
        str: The PlantUML text.
    """
    uml_lines = ["@startuml"]

    # Class definitions with typed fields
    for collection, fields in schema.items():
        uml_lines.append(f"class {collection} {{")
        for field, ftype in fields.items():
            uml_lines.append(f"  {field} : {ftype}")
        uml_lines.append("}")

    # Subcollection composition arrows
    for collection in schema:
        if "." in collection:
            parent = collection.rsplit(".", 1)[0]
            if parent in schema:
                uml_lines.append(f'{parent} *-- {collection} : subcollection')

    # FK relationship arrows
    for collection, rels in relationships.items():
        for field, related_collection in rels:
            uml_lines.append(f"{collection} --> {related_collection} : {field}")

    uml_lines.append("@enduml")
    plantuml_text = "\n".join(uml_lines)

    if generate_diagram:
        if output_file is None:
            raise ValueError("output_file must be specified if generate_diagram is True")
        generate_uml_diagram(plantuml_text, output_file)

    return plantuml_text
```

`generate_uml_diagram` stays unchanged.

**Step 2: Commit**

```bash
git add utils.py
git commit -m "feat: update PlantUML generation for typed fields and subcollections"
```

---

### Task 6: Update main.py

**Files:**
- Modify: `main.py`

**Step 1: Update main.py**

```python
from firebase_admin import credentials, firestore, initialize_app
from utils import get_schema, identify_relationships_llm, create_schema_graph_llm, generate_plantuml_text
from datetime import datetime

def main():
    # Initialize Firestore
    cred = credentials.ApplicationDefault()
    initialize_app(cred)
    db = firestore.client()

    # Extract schema with types and subcollections
    print("Extracting schema...\n")
    schema, reference_fields = get_schema(db)
    print("Schema extracted:")
    for collection, fields in schema.items():
        print(f"  {collection}:")
        for field, ftype in fields.items():
            print(f"    {field}: {ftype}")
    print()

    # Identify relationships (pre-seeded with known references)
    print("Identifying relationships...\n")
    relationships = identify_relationships_llm(schema, known_references=reference_fields)
    print("Relationships identified:")
    for collection, rels in relationships.items():
        if rels:
            print(f"  {collection}: {rels}")
    print()

    # Create pydot schema graph
    print("Creating schema graph...\n")
    graph_file = create_schema_graph_llm(schema, relationships)
    print(f"Schema graph saved to {graph_file}\n")

    # Generate PlantUML text and diagram
    print("Generating PlantUML diagram...\n")
    output_file = f'firestore_schema_llm_{datetime.now().strftime("%Y%m%d%H%M%S")}.png'
    plantuml_text = generate_plantuml_text(schema, relationships, generate_diagram=True, output_file=output_file)
    print("PlantUML text generated:")
    print(plantuml_text)

if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add main.py
git commit -m "feat: update main.py for typed schema and subcollection support"
```

---

### Task 7: Update requirements.txt and run all tests

**Files:**
- Modify: `requirements.txt`

**Step 1: Add pytest to requirements**

Add `pytest` to `requirements.txt`.

**Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pytest to requirements"
```
