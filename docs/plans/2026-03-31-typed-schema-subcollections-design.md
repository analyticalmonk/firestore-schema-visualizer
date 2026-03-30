# Design: Typed Schema Extraction + Subcollection Discovery

## Summary

Enhance the Firestore schema generator with two capabilities:
1. **Field type inference** - infer types from sampled documents instead of just field names
2. **Recursive subcollection discovery** - automatically find and include subcollections

## Schema Data Structure

Changes from `dict[str, list[str]]` to `dict[str, dict[str, str]]`:

```python
# Before
{"users": ["name", "email", "created_at"]}

# After
{"users": {"name": "string", "email": "string", "created_at": "timestamp", "profile_ref": "reference"}}
```

Subcollections use dot-notation keys:
```python
{"users": {...}, "users.posts": {"title": "string", "body": "string"}}
```

## Type Inference

Each field value maps to a type label:

| Python/Firestore type | Label |
|---|---|
| `str` | `string` |
| `int`, `float` | `number` |
| `bool` | `boolean` |
| `datetime` | `timestamp` |
| `DocumentReference` | `reference` |
| `GeoPoint` | `geopoint` |
| `list` | `array` |
| `dict` | `map` |
| `None` | `null` |

When multiple documents disagree on a field's type, the most common non-null type wins. Reference fields also record their target collection path for use as known relationships.

## Subcollection Discovery

- For each sampled document, call `document_ref.collections()` to find subcollections
- Deduplicate subcollection names across documents in the same parent collection
- Recurse up to `max_depth=3` (configurable)
- Dot-notation naming: `users.posts`, `users.posts.comments`
- Bounded by sample size (50 docs) and max depth

## Downstream Changes

### identify_relationships_llm
- Prompt includes field types for better accuracy
- Reference-type fields with known targets are pre-populated as relationships (skip LLM)
- LLM focuses on inferring name-based relationships only
- Fix existing `i += 1` bug

### create_schema_graph_llm
- Nodes display field names with types
- Subcollection parent-child edges labeled "subcollection"

### generate_plantuml_text
- Classes show typed fields (`name : string`)
- Subcollection relationships use composition arrow (`*--`) vs FK arrow (`-->`)

### main.py
- Passes through new schema format
- Uncomment pydot graph call
