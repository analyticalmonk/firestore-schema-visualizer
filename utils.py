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

def get_schema(db):
    """
    Retrieves the schema of a Firestore database.

    Args:
        db: The Firestore database object.

    Returns:
        A dictionary representing the schema of the database. The keys are the collection names,
        and the values are lists of field names present in each collection.
    """
    schema = {}
    collections = db.collections()
    for collection in collections:
        collection_name = collection.id
        schema[collection_name] = []
        docs = collection.limit(50).stream()
        for doc in docs:
            doc_data = doc.to_dict()
            for field in doc_data.keys():
                if field not in schema[collection_name]:
                    schema[collection_name].append(field)
    return schema

# Function to identify relationships using LLM with full document schema context
def identify_relationships_llm(schema):
    """
    Identifies foreign key relationships within the fields of each collection in the given schema.

    Args:
        schema (dict): A dictionary representing the schema of a Firestore database. Each key-value pair
                       represents a collection name and its corresponding fields.

    Returns:
        dict: A dictionary where each key represents a collection name and the value is a list of tuples.
              Each tuple contains the field name and the related collection name for a foreign key relationship.
    """
    relationships = {}
    schema_context = json.dumps(schema, indent=2)

    for collection, fields in schema.items():
        print(f"Collection: {collection}\n\n")
        relationships[collection] = []
        prompt = (
            f"Given the following schema:\n\n{schema_context}\n\n"
            f"Identify any foreign key relationships within the fields of the collection '{collection}'. "
            f"Provide the field name and the related collection if possible. Do not share any relationships that are not present in the provided schema." 
            f"If no relationships are found, respond with None and nothing else."
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512
        )
        related_collections_text = response.choices[0].message.content.strip()
        print(related_collections_text)
        
        if related_collections_text and ("None" not in related_collections_text):
            # Use another OpenAI call to format the response appropriately
            format_prompt = (
                "Given the identified relationships, convert this into a Python dict format where each entry is a tuple with the fields and related collection. Do not share anything other than the dict as an output."
                '{{"field_name": "related_collection"}}. Example: {{"userId": "users", "orderId": "orders"}}'
                "RELATIONSHIPS:"
                f"{related_collections_text}"
                "DICT OUTPUT:"
            )
            format_response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": format_prompt}],
                max_tokens=150
            )
            formatted_output = format_response.choices[0].message.content.strip()[10:-4]
            print(formatted_output)
            formatted_relationships = json.loads(formatted_output)

            formatted_relationships = [(k, v) for k, v in formatted_relationships.items()]
            relationships[collection].extend(formatted_relationships)

        i += 1
        print("\n\n")
    
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