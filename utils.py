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


def get_schema(db, max_depth=3, sample_size=50, collections=None):
    """
    Retrieve the schema of a Firestore database with inferred field types
    and recursive subcollection discovery.

    Args:
        db: The Firestore database client.
        max_depth: Maximum subcollection nesting depth to explore (default 3).
        sample_size: Number of documents to sample per collection (default 50).
        collections: Optional set of top-level collection names to scan. If None, scans all.

    Returns:
        A tuple of (schema, reference_fields):
        - schema: dict[str, dict[str, str]] - collection path -> {field_name: type_label}
        - reference_fields: dict[str, list[tuple[str, str]]] - collection path -> [(field, target_collection)]
    """
    schema = {}
    reference_fields = {}

    def _process_collection(collection_ref, path_prefix, depth):
        col_path = f"{path_prefix}.{collection_ref.id}" if path_prefix else collection_ref.id
        indent = "  " * depth
        print(f"{indent}Scanning collection: {col_path}")
        field_type_counts = {}  # {field_name: {type_label: count}}
        seen_subcollections = {}  # {name: collection_ref}

        docs = list(collection_ref.limit(sample_size).stream())
        print(f"{indent}  Sampled {len(docs)} docs")
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

            # Discover subcollections (only check first doc to reduce API calls)
            if depth < max_depth and not seen_subcollections:
                sub_col_refs = list(doc.reference.collections())
                for sub_col in sub_col_refs:
                    seen_subcollections[sub_col.id] = sub_col
                if seen_subcollections:
                    print(f"{indent}  Found subcollections: {set(seen_subcollections.keys())}")

        # Recurse into discovered subcollections after processing all docs
        if depth < max_depth:
            for sub_col_name, sub_col_ref in seen_subcollections.items():
                _process_collection(sub_col_ref, col_path, depth + 1)

        # Merge type counts into final types
        schema[col_path] = {
            field: merge_field_types(counts)
            for field, counts in field_type_counts.items()
        }

    for collection in db.collections():
        if collections and collection.id not in collections:
            continue
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
            f"Identify fields that are foreign keys - fields that store an ID or key used to look up "
            f"a document in another collection. Typical patterns: fields ending in _id, _ref, Id, Ref, "
            f"or fields named exactly like a collection in singular form (e.g., 'user' -> 'users').\n\n"
            f"Do NOT flag fields that merely contain data that also exists in another collection. "
            f"For example, an 'email' field stores a value, not a foreign key, even if another "
            f"collection also has email fields.\n\n"
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
        node = pydot.Node(f'"{collection}"', label=label)
        graph.add_node(node)

    # Add subcollection parent-child edges
    for collection in schema:
        if "." in collection:
            parent = collection.rsplit(".", 1)[0]
            if parent in schema:
                edge = pydot.Edge(f'"{parent}"', f'"{collection}"', label="subcollection", style="dashed")
                graph.add_edge(edge)

    # Add FK relationship edges
    for collection, rels in relationships.items():
        for field, related_collection in rels:
            edge = pydot.Edge(f'"{collection}"', f'"{related_collection.strip()}"', label=field.strip())
            graph.add_edge(edge)

    output_file = f'firestore_schema_llm_{datetime.now().strftime("%Y%m%d%H%M%S")}.png'
    graph.write_png(output_file)
    return output_file

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
        uml_lines.append(f'class "{collection}" {{')
        for field, ftype in fields.items():
            uml_lines.append(f"  {field} : {ftype}")
        uml_lines.append("}")

    # Subcollection composition arrows
    for collection in schema:
        if "." in collection:
            parent = collection.rsplit(".", 1)[0]
            if parent in schema:
                uml_lines.append(f'"{parent}" *-- "{collection}" : subcollection')

    # FK relationship arrows
    for collection, rels in relationships.items():
        for field, related_collection in rels:
            uml_lines.append(f'"{collection}" --> "{related_collection}" : {field}')

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

    try:
        plantuml.processes_file(temp_file_path)
        generated_file = temp_file_path.replace(".puml", ".png")
        os.rename(generated_file, output_file)
    except Exception as e:
        print(f"Warning: PlantUML server rendering failed ({e}). "
              f"The PlantUML text has been saved to {temp_file_path} - "
              f"you can paste it into https://www.plantuml.com/plantuml/uml/ to render manually.")
        return
    os.remove(temp_file_path)
    print(f"UML diagram saved as {output_file}")