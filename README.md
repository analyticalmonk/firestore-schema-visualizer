# Firestore Schema Diagram Generator

## Description
This project extracts schema information from Firestore, identifies relationships using OpenAI, and generates a schema diagram.

## Setup

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/your-repository.git
    cd your-repository
    ```

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

1. Extract schema information:
    ```sh
    python schema_extractor.py
    ```

2. Identify relationships:
    ```sh
    python relationship_identifier.py
    ```

3. Generate schema diagram:
    ```sh
    python schema_diagram.py
    ```

## License
[MIT License](LICENSE)
