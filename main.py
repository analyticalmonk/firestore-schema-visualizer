from firebase_admin import credentials, firestore, initialize_app
from utils import get_schema, identify_relationships_llm, create_schema_graph_llm, generate_plantuml_text
from datetime import datetime

def main():
    """
    Entry point of the Firestore Schema Generator.

    This function initializes Firestore, extracts the schema, identifies relationships,
    creates a schema graph, generates PlantUML text and diagram, and prints the results.

    Returns:
        None
    """
    # Initialize Firestore
    cred = credentials.ApplicationDefault()
    initialize_app(cred)
    db = firestore.client()

    # Extract schema
    print("Extracting schema...\n")
    schema = get_schema(db)
    print("Schema extracted:")
    print(schema)

    # Identify relationships
    print("Identifying relationships...\n")
    relationships = identify_relationships_llm(schema)
    print("Relationships identified:")
    print(relationships)

    # # Create schema graph
    # print("Creating schema graph...\n")
    # create_schema_graph_llm(schema, relationships)
    # print("Schema graph created.")

    # Generate PlantUML text and diagram
    print("Generating PlantUML text and diagram...\n")
    output_file = f'firestore_schema_llm_{datetime.now().strftime("%Y%m%d%H%M%S")}.png'
    plantuml_text = generate_plantuml_text(schema, relationships, generate_diagram=True, output_file=output_file)
    print("PlantUML text generated:")
    print(plantuml_text)

if __name__ == "__main__":
    main()
