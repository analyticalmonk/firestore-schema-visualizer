import os
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize the app with the environment variable
cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred)

db = firestore.client()

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

schema = get_schema(db)