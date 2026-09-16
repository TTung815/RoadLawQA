# History-aware retrieval

Run commands from the repository root using the existing virtual environment.

```bash
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
curl --fail http://127.0.0.1:8000/api/v1/health
```

For queries requiring contextualization, configure `GEMINI_API_KEY` in the process
environment or the repository-root `.env`. `GEMINI_MODEL_NAME` optionally overrides
the current default, `gemini-2.5-flash`. Configuration does not mutate `os.environ`.
The service reads LLM configuration on its first retrieval request and caches the
composed service; restart the server after configuration changes.

Retrieval requires the existing Weaviate instance, indexed `LawChunks`, BM25
resources, and embedding/reranker models. Start Weaviate with:

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d
```

The adapter preserves `backend/retriever_custom.py` unchanged: that module uses
default local Weaviate ports 8080/50051 and a working-directory-relative BM25 path.
V2 retrieval settings do not override those legacy choices. Its first lazy import
and actual retrieval run in a worker thread. Health initializes none of these resources.

Compose uses `WEAVIATE_CLUSTER_HOSTNAME` from the explicitly supplied `.env`, with
`node1` as the default for fresh data. Keep this name stable for an existing volume.
If an older index reports `resolve node name "..." to host`, use that persisted node
name as `WEAVIATE_CLUSTER_HOSTNAME` rather than deleting or rebuilding the index.

```bash
curl --fail http://127.0.0.1:8000/api/v1/retrieve \
  -H 'Content-Type: application/json' \
  --data '{"current_query":"Còn ô tô thì sao?","chat_history":[{"role":"user","content":"Xe máy vượt đèn đỏ phạt bao nhiêu?"}],"top_k":3}'
```

The response contains `original_query`, `standalone_query`, and `chunks`.
Each chunk includes its ID, text, enriched text, citation, score, and metadata.
`top_k` must be between 1 and 20. History accepts chronological user/assistant text
messages. No answer is generated. Provider and retrieval failures propagate as server
errors; there is no fallback to the original query or empty success response.

With empty history, the trimmed current query is used directly without an LLM call.
With any nonempty history, structured contextualization runs before retrieval.
There is no keyword-based independence or relevance check. The prompt determines
which history is relevant, resolves references, and preserves standalone questions
without adding unrelated context. Nonempty-history requests require valid provider
credentials even when the current question appears complete. Real-model semantic
quality still requires evaluation.

```bash
# Default suite: integration tests are deselected.
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/unit -q

# Existing live legacy-retrieval smoke test, explicitly opt-in.
.venv/bin/python -m pytest tests/integration -m integration -q
```

Default tests use fake providers, in-memory HTTP transports, and fake retrieval
functions. They require no credentials, external services, or model loading.
The live smoke test covers legacy retrieval; it does not evaluate live Gemini contextualization.
