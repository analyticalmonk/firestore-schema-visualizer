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
