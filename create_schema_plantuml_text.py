from datetime import datetime
import os
import tempfile
from plantuml import PlantUML

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

# # Example usage
# schema = {
#     'users': ['name', 'email', 'posts'],
#     'posts': ['title', 'content', 'author']
# }
# relationships = {
#     'users': [('posts', 'author')],
#     'posts': [('author', 'users')]
# }
output_file = f'firestore_schema_llm_{datetime.now().strftime("%Y%m%d%H%M%S")}.png'
plantuml_text = generate_plantuml_text(schema, relationships, generate_diagram=True, output_file=output_file)
print(plantuml_text)