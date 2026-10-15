"""HTTP client for the RoadLawQA API; no Streamlit code here."""

import os

import httpx

# A conversation that no longer exists (HTTP 404), as opposed to an outage (None).
MISSING = object()


def api_url() -> str:
    return os.environ.get("ROADLAWQA_API_URL", "http://127.0.0.1:8000").rstrip("/")


def conversations_url() -> str:
    return f"{api_url()}/api/v1/conversations"


def fetch(url: str):
    """GET JSON: MISSING for 404, None when the API is unreachable or invalid."""
    try:
        response = httpx.get(url, timeout=30)
        if response.status_code == 404:
            return MISSING
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return None


def list_conversations():
    return fetch(conversations_url())


def get_conversation(conversation_id: str):
    return fetch(f"{conversations_url()}/{conversation_id}")


def create_conversation() -> str:
    """Raises httpx.HTTPError, ValueError or KeyError when the API cannot create one."""
    response = httpx.post(conversations_url(), timeout=30)
    response.raise_for_status()
    return response.json()["id"]


def delete_conversation(conversation_id: str) -> None:
    httpx.delete(f"{conversations_url()}/{conversation_id}", timeout=30).raise_for_status()


def send_message(conversation_id: str, content: str, top_k: int = 10) -> None:
    """The API reads earlier turns from storage and saves both new turns."""
    httpx.post(f"{conversations_url()}/{conversation_id}/messages",
               json={"content": content, "top_k": top_k}, timeout=300).raise_for_status()


def inspect_retrieval(query: str, top_k: int) -> dict:
    response = httpx.post(f"{api_url()}/api/v1/retrieve/inspect",
                          json={"current_query": query, "top_k": top_k}, timeout=300)
    response.raise_for_status()
    return response.json()
