# Firestore Schema and Relationships Visualization

This project provides tools to extract the schema of a Firestore database, identify relationships between collections, and generate visual representations of the schema and relationships using PlantUML and pydot.

## Features

- **Extract Firestore Schema**: Retrieve the schema of a Firestore database, including collection names and their fields.
- **Identify Relationships**: Use OpenAI's GPT-4 to identify foreign key relationships between collections.
- **Generate Schema Graph**: Create a visual representation of the Firestore schema and relationships using pydot.
- **Generate PlantUML Text**: Generate PlantUML text for the schema and relationships, with an option to create a UML diagram.

## Installation

1. Clone the repository:

2. Create a virtual environment and activate it:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install dependencies:
    ```sh
    pip install -r requirements.txt
    ```

4. Set up environment variables:
    ```sh
    export OPENAI_API_KEY='your-api-key'
    ```

## Usage

To run the complete workflow of extracting the schema, identifying relationships, generating a schema graph, and optionally creating a PlantUML diagram, use the `main.py` script:

## Functions

#### `get_schema`

```python
def get_schema(db):
    """
    Retrieves the schema of a Firestore database.

    Args:
        db: The Firestore database object.

    Returns:
        dict: A dictionary representing the schema of the database. The keys are the collection names,
              and the values are lists of field names present in each collection.
    """
```

#### `identify_relationships_llm`

```python
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
```

#### `generate_plantuml_text`

```python
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
```

#### `generate_uml_diagram`

```python
def generate_uml_diagram(plantuml_text, output_file):
    """
    Generates a UML diagram from PlantUML text.
    
    Args:
        plantuml_text (str): The PlantUML text.
        output_file (str): The path to the output file.
    
    Returns:
        None
    """
```

#### `create_schema_graph_llm`

```python
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

    This function creates a directed graph using the pydot library to visualize the schema and relationships
    between Firestore collections. Each collection is represented as a node, and each relationship is represented
    as an edge with a label indicating the field name.

    The resulting graph is saved as a PNG image named 'firestore_schema_llm_<timestamp>.png' in the current directory.
    """
```

## License
[MIT License](LICENSE)