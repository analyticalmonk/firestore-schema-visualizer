import json
from unittest.mock import patch, MagicMock
from utils import identify_relationships_llm, _make_openai_caller, _make_anthropic_caller


SCHEMA = {
    "users": {"name": "string", "age": "number"},
    "posts": {"title": "string", "user_id": "string"},
}


def _mock_llm_caller(response_text):
    """Return a callable that returns the given response text."""
    return lambda prompt: response_text


def test_openai_provider_called():
    llm_response = json.dumps({"user_id": "users"})
    with patch("utils._make_openai_caller", return_value=_mock_llm_caller(llm_response)):
        rels = identify_relationships_llm(SCHEMA, llm_provider="openai")
    assert ("user_id", "users") in rels["posts"]


def test_anthropic_provider_called():
    llm_response = json.dumps({"user_id": "users"})
    with patch("utils._make_anthropic_caller", return_value=_mock_llm_caller(llm_response)):
        rels = identify_relationships_llm(SCHEMA, llm_provider="anthropic")
    assert ("user_id", "users") in rels["posts"]


def test_known_references_prepopulated():
    known = {"posts": [("author_ref", "users")]}
    llm_response = json.dumps({})
    with patch("utils._make_openai_caller", return_value=_mock_llm_caller(llm_response)):
        rels = identify_relationships_llm(SCHEMA, known_references=known, llm_provider="openai")
    assert ("author_ref", "users") in rels["posts"]


def test_skips_llm_when_all_fields_resolved():
    schema = {"posts": {"author_ref": "reference"}}
    known = {"posts": [("author_ref", "users")]}
    mock_caller = MagicMock()
    with patch("utils._make_openai_caller", return_value=mock_caller):
        rels = identify_relationships_llm(schema, known_references=known, llm_provider="openai")
    mock_caller.assert_not_called()
    assert ("author_ref", "users") in rels["posts"]


def test_ignores_target_not_in_schema():
    llm_response = json.dumps({"user_id": "nonexistent_collection"})
    with patch("utils._make_openai_caller", return_value=_mock_llm_caller(llm_response)):
        rels = identify_relationships_llm(SCHEMA, llm_provider="openai")
    assert rels["posts"] == []


def test_invalid_provider_raises():
    try:
        identify_relationships_llm(SCHEMA, llm_provider="invalid")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown LLM provider" in str(e)


def test_make_openai_caller():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"user_id": "users"}'
    with patch("openai.OpenAI") as MockClient:
        MockClient.return_value.chat.completions.create.return_value = mock_response
        with patch("config.OPENAI_API_KEY", "test-key"):
            caller = _make_openai_caller()
            result = caller("test prompt")
    assert result == '{"user_id": "users"}'


def test_make_anthropic_caller():
    mock_content = MagicMock()
    mock_content.text = '{"user_id": "users"}'
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_response
        with patch("config.ANTHROPIC_API_KEY", "test-key"):
            caller = _make_anthropic_caller()
            result = caller("test prompt")
    assert result == '{"user_id": "users"}'
