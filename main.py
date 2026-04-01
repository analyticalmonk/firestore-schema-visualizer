import sys
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
    args = parser.parse_args()

    # Validate OpenAI API key upfront if LLM will be used
    if not args.skip_llm and (not OPENAI_API_KEY or OPENAI_API_KEY == "your-api-key"):
        print("Error: OPENAI_API_KEY is not set. Either set it via environment variable or use --skip-llm.")
        sys.exit(1)

    # Initialize Firestore
    cred = credentials.ApplicationDefault()
    initialize_app(cred)
    db = firestore.client()

    # Extract schema with types and subcollections
    print("Extracting schema...\n")
    schema, reference_fields = get_schema(db, max_depth=args.max_depth, sample_size=args.sample_size)
    print("\nSchema extracted:")
    for collection, fields in schema.items():
        print(f"  {collection}:")
        for field, ftype in fields.items():
            print(f"    {field}: {ftype}")
    print()

    # Identify relationships
    if args.skip_llm:
        print("Skipping LLM - using reference-type fields only.\n")
        relationships = {col: refs for col, refs in reference_fields.items()}
        for col in schema:
            if col not in relationships:
                relationships[col] = []
    else:
        print("Identifying relationships...\n")
        relationships = identify_relationships_llm(schema, known_references=reference_fields)
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
