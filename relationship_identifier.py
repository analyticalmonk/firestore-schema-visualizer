from openai import OpenAI
import json

openai_api_key = ''
client = OpenAI(api_key=openai_api_key)

# # OpenAI tool calling sample
# tools = [{
#     "type": "function",
#     "function": {
#         "name": "create_schema_graph_llm",
#         "description": "Creates a schema graph for Firestore collections and their relationships.",
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "schema": {
#                     "type": "object",
#                     "description": "A dictionary representing the Firestore schema, where the keys are collection names and the values are dictionaries representing the fields of each collection."
#                 },
#                 "relationships": {
#                     "type": "object",
#                     "description": "A dictionary representing the relationships between collections, where the keys are collection names and the values are lists of tuples representing the fields and related collections."
#                 }
#             },
#             "required": ["schema", "relationships"]
#         }
#     }
# }]

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

    i = 0
    for collection, fields in schema.items():
        print(f"Collection: {collection}\n\n")
        if i == 0:
            i += 1
            continue
        if i > 2:
            break
        relationships[collection] = []
        prompt = (
            f"Given the following schema:\n\n{schema_context}\n\n"
            f"Identify any foreign key relationships within the fields of the collection '{collection}'. "
            f"Provide the field name and the related collection if possible."
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512
        )
        related_collections_text = response.choices[0].message.content.strip()
        print(related_collections_text)
        
        if related_collections_text:
            # Use another OpenAI call to format the response appropriately
            format_prompt = (
                "Given the identified relationships, convert this into a Python dict format where each entry is a tuple with the fields and related collection. Do not share anything other than the dict as an output"
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

# Example usage with the schema extracted
relationships = identify_relationships_llm(schema)
print(relationships)
