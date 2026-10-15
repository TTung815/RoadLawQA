"""Prepare a clean machine for serving: download the pinned models, then build the index.

    python -m ingestion.bootstrap        (in Docker: the compose `bootstrap` service)

Both steps are idempotent. Models are fetched at the exact commits the corpus
and settings lock; an index that already exists is verified, never rebuilt.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from configs.settings import Settings
from ingestion.legal_registry import read_json
from ingestion.structured_corpus import DEFAULT_BUNDLE

# Remote modeling code of the embedding model; the index was built with this commit.
NEW_IMPL_REVISION = "40ced75c3017eb27626c9d4ea981bde21a2662f4"
MODEL_FILES = ["*.json", "*.safetensors", "*.py", "*.model"]


def pinned_models(settings: Settings) -> dict[str, str]:
    manifest = read_json(DEFAULT_BUNDLE / "manifest.json")
    return {
        "Alibaba-NLP/gte-multilingual-base": manifest["embedding_revision"],
        "Alibaba-NLP/new-impl": NEW_IMPL_REVISION,
        "BAAI/bge-reranker-v2-m3": settings.reranker_revision,
    }


def pin_main_ref(cache_dir: Path, repo: str, revision: str) -> None:
    """Loaders read the cached `main` ref offline, so point it at the pinned commit."""
    ref = cache_dir / f"models--{repo.replace('/', '--')}" / "refs" / "main"
    if ref.exists():
        if ref.read_text().strip() != revision:
            raise ValueError(f"cached {repo} is at another revision; use a separate HF cache")
        return
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(revision)


def download_models(settings: Settings) -> None:
    from huggingface_hub import constants, snapshot_download

    cache_dir = Path(constants.HF_HUB_CACHE)
    for repo, revision in pinned_models(settings).items():
        print(f"Model {repo}@{revision[:8]}", flush=True)
        snapshot_download(repo, revision=revision, allow_patterns=MODEL_FILES)
        pin_main_ref(cache_dir, repo, revision)


def wait_for_weaviate(settings: Settings, timeout_s: float = 120) -> None:
    import httpx

    url = f"http://{settings.weaviate_host}:{settings.weaviate_port}/v1/.well-known/ready"
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            if httpx.get(url, timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline:
            raise TimeoutError("Weaviate did not become ready")
        time.sleep(2)


def main() -> None:
    from ingestion.structured_index import build_index

    settings = Settings()
    download_models(settings)
    wait_for_weaviate(settings)
    receipt = build_index(settings.weaviate_host, settings.weaviate_port, settings.weaviate_grpc_port)
    print(json.dumps({"collection": receipt["collection"], "chunks": receipt["chunks"]}), flush=True)
    print("Ready: start the stack with `docker compose ... up -d`.", flush=True)


if __name__ == "__main__":
    main()
