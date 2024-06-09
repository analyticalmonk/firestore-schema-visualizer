import pydot

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
            'users': {
                'name': 'string',
                'email': 'string',
                'posts': 'subcollection'
            },
            'posts': {
                'title': 'string',
                'content': 'string',
                'author': 'reference(users)'
            }
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
    
    graph.write_png('firestore_schema_llm.png')

create_schema_graph_llm(schema, relationships)