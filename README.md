# Firestore Schema and Relationships Visualization

Extract the schema of a Firestore database, identify relationships between collections, and generate visual representations of the schema and relationships using PlantUML and pydot.

*Note: this is an exploratory project and not meant for production usage.*

## Features

- **Extract Firestore Schema**: Retrieve the schema of a Firestore database, including collection names, field names, and inferred field types (string, number, boolean, timestamp, reference, etc.).
- **Subcollection Discovery**: Recursively discover and include subcollections (e.g., `users.posts.comments`).
- **Identify Relationships**: Use OpenAI's GPT-4o to identify foreign key relationships between collections. DocumentReference fields are detected automatically without the LLM.
- **Generate Schema Graph**: Create a visual representation of the Firestore schema and relationships using pydot.
- **Generate PlantUML Diagram**: Generate PlantUML class diagrams with typed fields and relationship arrows.

## Installation

1. Clone the repository.

2. Create a virtual environment and activate it:
    ```sh
    python -m venv venv
    source venv/bin/activate
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

```sh
# Full run with defaults
python main.py

# Quick run - fewer samples, no subcollections, skip LLM
python main.py --sample-size 10 --max-depth 0 --skip-llm

# Only top-level collections with PlantUML output
python main.py --max-depth 0 --format plantuml

# Deeper subcollection discovery with smaller sample
python main.py --max-depth 5 --sample-size 20
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--sample-size N` | 50 | Number of documents to sample per collection |
| `--max-depth N` | 3 | Maximum subcollection nesting depth (0 to skip subcollections) |
| `--skip-llm` | off | Skip LLM relationship detection (only use reference-type fields) |
| `--format` | all | Output format: `all`, `plantuml`, or `pydot` |

### Quick mode

For a fast overview without LLM costs or subcollection crawling:

```sh
python main.py --sample-size 10 --max-depth 0 --skip-llm
```

## Tests

```sh
python -m pytest tests/ -v
```

## License
[MIT License](LICENSE)