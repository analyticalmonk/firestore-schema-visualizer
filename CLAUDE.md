# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Exploratory tool that extracts a Firestore database schema, uses OpenAI GPT-4o to identify foreign key relationships between collections, and generates visual diagrams (pydot PNG graphs and PlantUML class diagrams). Not intended for production use.

## Setup and Running

```sh
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY='...'
# Firestore uses Application Default Credentials
python main.py
```

Tests: `python -m pytest tests/ -v`. No linter config or build steps.

## Architecture

**Entry point:** `main.py` - initializes Firestore via Application Default Credentials, then runs the pipeline: extract schema -> identify relationships -> generate diagrams.

**Core logic:** `utils.py` - contains all four pipeline functions consolidated from the standalone scripts:
- `infer_field_type(value)` / `merge_field_types(type_counts)` - type inference helpers
- `get_schema(db, max_depth=3, sample_size=50)` - samples docs per collection to infer field names and types, recursively discovers subcollections (dot-notation paths like `users.posts`), returns `(schema, reference_fields)` tuple
- `identify_relationships_llm(schema, known_references=None)` - single OpenAI call per collection with JSON mode; pre-populates known reference-type relationships, LLM identifies remaining name-based FKs
- `create_schema_graph_llm(schema, relationships)` - renders a pydot directed graph to timestamped PNG
- `generate_plantuml_text(schema, relationships)` / `generate_uml_diagram(plantuml_text, output_file)` - generates PlantUML class diagram text and optionally renders it via the public PlantUML server

**Config:** `config.py` - reads `OPENAI_API_KEY` from environment.

**`scripts/` directory:** Earlier standalone versions of each pipeline step. These are not used by `main.py` - they were the original exploratory scripts before consolidation into `utils.py`. Some have hardcoded state and top-level execution code.

## Key Data Structures

- **schema**: `dict[str, dict[str, str]]` - collection path -> {field_name: type_label}. Subcollections use dot-notation keys (e.g., `users.posts`).
- **reference_fields**: `dict[str, list[tuple[str, str]]]` - collection path -> [(field, target_collection)] for DocumentReference-type fields discovered during schema extraction
- **relationships**: `dict[str, list[tuple[str, str]]]` - collection name -> list of (field_name, related_collection) tuples (combines known references + LLM-identified FKs)
