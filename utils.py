import os
import json
import pydot
import tempfile
from openai import OpenAI
from plantuml import PlantUML
from datetime import datetime
from config import OPENAI_API_KEY
# from firebase_admin import credentials, firestore, initialize_app

client = OpenAI(api_key=OPENAI_API_KEY)


def infer_field_type(value):
    """Map a Python/Firestore value to a type label string."""
    if value is None:
        return "null"
    if isinstance(value, bool):
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
            if not doc_data:
                continue
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


def create_schema_graph_llm(schema, relationships):
    """
    Creates a schema graph for Firestore collections and their relationships.

    Args:
        schema (dict): A dictionary representing the Firestore schema, where the keys are collection names
            and the values are dictionaries representing the fields of each collection.
        relationships (dict): A dictionary representing the relationships between collections, where the keys are
            collection names and the values are lists of tuples representing the fields and related collections.

    Returns:
        None

    Raises:
        None

    Example:
        schema = {
            'users': [
                'name'
                'email',
                'posts'
            ],
            'posts': [
                'title',
                'content',
                'author'
            ]
        }
        relationships = {
            'users': [('posts', 'author')],
            'posts': [('author', 'users')]
        }
        create_schema_graph_llm(schema, relationships)

    This function creates a directed graph using the pydot library to visualize the schema and relationships
    between Firestore collections. Each collection is represented as a node, and each relationship is represented
    as an edge with a label indicating the field name.

    The resulting graph is saved as a PNG image named 'firestore_schema_llm.png' in the current directory.
    """
    graph = pydot.Dot(graph_type='digraph')

    for collection, fields in schema.items():
        node = pydot.Node(collection)
        graph.add_node(node)
        
        for field, related_collection in relationships.get(collection, []):
            edge = pydot.Edge(collection, related_collection.strip(), label=field.strip())
            graph.add_edge(edge)

    # Append filename with timestamp
    graph.write_png(f'firestore_schema_llm_{datetime.now().strftime("%Y%m%d%H%M%S")}.png')

def generate_plantuml_text(schema, relationships, generate_diagram=False, output_file=None):
    """
    Generates PlantUML text for Firestore collections and their relationships.
    
    Args:
        schema (dict): A dictionary representing the Firestore schema, where the keys are collection names
                       and the values are lists representing the fields of each collection.
        relationships (dict): A dictionary representing the relationships between collections, where the keys are
                              collection names and the values are lists of tuples representing the fields and related collections.
        generate_diagram (bool): Whether to generate a UML diagram. Default is False.
        output_file (str): The path to the output file for the UML diagram. Required if generate_diagram is True.
    
    Returns:
        str: The PlantUML text representing the schema and relationships.
    """
    uml_lines = ["@startuml"]

    # Create class definitions for each collection
    for collection, fields in schema.items():
        uml_lines.append(f"class {collection} {{")
        if isinstance(fields, list):
            for field in fields:
                uml_lines.append(f"  {field}")
        else:
            uml_lines.append("  // Invalid schema format")
        uml_lines.append("}")

    # Create relationships
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

def generate_uml_diagram(plantuml_text, output_file):
    """
    Generates a UML diagram from PlantUML text.
    
    Args:
        plantuml_text (str): The PlantUML text.
        output_file (str): The path to the output file.
    
    Returns:
        None
    """
    plantuml = PlantUML(url='http://www.plantuml.com/plantuml/img/')

    # Write the PlantUML text to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".puml") as temp_file:
        temp_file.write(plantuml_text.encode('utf-8'))
        temp_file_path = temp_file.name

    # Generate the UML diagram from the temporary file
    plantuml.processes_file(temp_file_path)

    # Move the generated diagram to the specified output file
    generated_file = temp_file_path.replace(".puml", ".png")
    os.rename(generated_file, output_file)
    os.remove(temp_file_path)
    print(f"UML diagram saved as {output_file}")