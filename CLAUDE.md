# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Exploratory tool that extracts a Firestore database schema, uses an LLM (OpenAI GPT-4o or Anthropic Claude) to identify foreign key relationships between collections, and generates visual diagrams (pydot PNG graphs and PlantUML class diagrams). Not intended for production use.

## Setup and Running

```sh
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY='...'       # for --llm-provider openai (default)
export ANTHROPIC_API_KEY='...'    # for --llm-provider anthropic
# Firestore uses Application Default Credentials
python main.py
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--sample-size N` | 50 | Documents to sample per collection |
| `--max-depth N` | 3 | Subcollection nesting depth (0 = skip) |
| `--skip-llm` | off | Skip LLM, use reference-type fields only |
| `--format` | all | `all`, `plantuml`, or `pydot` |
| `--no-export-json` | off | Skip JSON schema export |
| `--collections` | all | Comma-separated collection filter |
| `--llm-provider` | openai | `openai` or `anthropic` |

Quick run without LLM or subcollections: `python main.py --sample-size 10 --max-depth 0 --skip-llm`

### Tests

```sh
python -m pytest tests/ -v          # all tests
python -m pytest tests/test_type_inference.py -v   # single file
python -m pytest tests/ -v -k test_basic_typed_schema  # single test
```

No linter config or build steps.

## Architecture

**Pipeline:** `main.py` orchestrates: extract schema -> export JSON -> identify relationships -> generate diagrams. Each step is independent - the JSON export happens before relationship detection so schema is saved even if later steps fail. LLM failure is non-fatal (falls back to reference-only relationships).

**Core logic:** `utils.py` - all pipeline functions:
- `get_schema(db, ...)` - samples docs per collection, infers field types, recursively discovers subcollections (dot-notation paths like `users.posts`), returns `(schema, reference_fields)` tuple
- `identify_relationships_llm(schema, known_references)` - one OpenAI call per collection with JSON mode; pre-populates known DocumentReference relationships, LLM finds remaining name-based FKs
- `create_schema_graph_llm(schema, relationships)` - pydot directed graph to timestamped PNG
- `generate_plantuml_text(schema, relationships)` / `generate_uml_diagram(plantuml_text, output_file)` - PlantUML class diagram, optionally rendered via public PlantUML server

**Config:** `config.py` - reads `OPENAI_API_KEY` from environment.

**`scripts/` directory:** Legacy standalone scripts, not used by `main.py`. Some have hardcoded state and top-level execution code.

## Key Data Structures

- **schema**: `dict[str, dict[str, str]]` - collection path -> {field_name: type_label}. Subcollections use dot-notation keys (e.g., `users.posts`).
- **reference_fields**: `dict[str, list[tuple[str, str]]]` - collection path -> [(field, target_collection)] for DocumentReference fields found during extraction
- **relationships**: `dict[str, list[tuple[str, str]]]` - collection -> [(field_name, related_collection)] combining known references + LLM-identified FKs

## Relationship Detection

Two layers: (1) Firestore `DocumentReference` fields detected automatically during schema extraction - zero cost. (2) LLM examines field names to infer string/number fields that act as foreign keys (e.g., `user_id` -> `users`). `--skip-llm` disables layer 2 only.
