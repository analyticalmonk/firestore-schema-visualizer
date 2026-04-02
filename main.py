import sys
import json
import argparse
from firebase_admin import credentials, firestore, initialize_app
from utils import get_schema, identify_relationships_llm, create_schema_graph_llm, generate_plantuml_text
from config import OPENAI_API_KEY
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="Extract Firestore schema and generate relationship diagrams.")
    parser.add_argument("--sample-size", type=int, default=50,
                        help="Number of documents to sample per collection (default: 50)")
    parser.add_argument("--max-depth", type=int, default=3,
                        help="Maximum subcollection nesting depth (default: 3, 0 to skip subcollections)")
    parser.add_argument("--skip-llm", action="store_true",
                        help="Skip LLM relationship detection (only use reference-type fields)")
    parser.add_argument("--format", choices=["all", "plantuml", "pydot"], default="all",
                        help="Output format (default: all)")
    parser.add_argument("--no-export-json", action="store_true",
                        help="Skip exporting schema to a JSON file")
    parser.add_argument("--collections", type=str,
                        help="Comma-separated list of collections to include in diagrams (e.g., users,posts,comments)")
    args = parser.parse_args()

    # Check OpenAI API key upfront if LLM will be used
    if not args.skip_llm and (not OPENAI_API_KEY or OPENAI_API_KEY == "your-api-key"):
        print("Warning: OPENAI_API_KEY is not set. LLM relationship detection will be skipped.")
        print("Set the environment variable or pass --skip-llm to silence this warning.\n")
        args.skip_llm = True

    # Initialize Firestore
    cred = credentials.ApplicationDefault()
    initialize_app(cred)
    db = firestore.client()

    # Extract schema with types and subcollections
    print("Extracting schema...\n")
    selected_collections = set(args.collections.split(",")) if args.collections else None
    schema, reference_fields = get_schema(db, max_depth=args.max_depth, sample_size=args.sample_size,
                                          collections=selected_collections)
    print("\nSchema extracted:")
    for collection, fields in schema.items():
        print(f"  {collection}:")
        for field, ftype in fields.items():
            print(f"    {field}: {ftype}")
    print()

    # Export schema to JSON immediately so it's saved even if later steps fail
    if not args.no_export_json:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        json_file = f"firestore_schema_{timestamp}.json"
        export_data = {
            "schema": schema,
            "reference_fields": {col: [(f, t) for f, t in refs] for col, refs in reference_fields.items()}
        }
        with open(json_file, "w") as f:
            json.dump(export_data, f, indent=2)
        print(f"Schema exported to {json_file}\n")

    # Identify relationships
    if args.skip_llm:
        print("Skipping LLM - using reference-type fields only.\n")
        relationships = {col: refs for col, refs in reference_fields.items()}
        for col in schema:
            if col not in relationships:
                relationships[col] = []
    else:
        print("Identifying relationships...\n")
        try:
            relationships = identify_relationships_llm(schema, known_references=reference_fields)
        except Exception as e:
            print(f"Warning: LLM relationship detection failed ({e}).")
            print("Falling back to reference-type fields only.\n")
            relationships = {col: refs for col, refs in reference_fields.items()}
            for col in schema:
                if col not in relationships:
                    relationships[col] = []
    print("Relationships identified:")
    for collection, rels in relationships.items():
        if rels:
            print(f"  {collection}: {rels}")
    print()

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Create pydot schema graph
    if args.format in ("all", "pydot"):
        print("Creating schema graph...\n")
        graph_file = create_schema_graph_llm(schema, relationships)
        print(f"Schema graph saved to {graph_file}\n")

    # Generate PlantUML text and diagram
    if args.format in ("all", "plantuml"):
        print("Generating PlantUML diagram...\n")
        output_file = f"firestore_schema_llm_{timestamp}.png"
        plantuml_text = generate_plantuml_text(schema, relationships, generate_diagram=True, output_file=output_file)
        print("PlantUML text generated:")
        print(plantuml_text)


if __name__ == "__main__":
    main()
