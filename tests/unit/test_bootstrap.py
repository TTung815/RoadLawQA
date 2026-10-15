import pytest

from configs.settings import Settings
from ingestion.bootstrap import pin_main_ref, pinned_models


def test_models_are_pinned_to_the_corpus_and_settings_revisions():
    models = pinned_models(Settings())

    assert set(models) == {"Alibaba-NLP/gte-multilingual-base", "Alibaba-NLP/new-impl", "BAAI/bge-reranker-v2-m3"}
    assert models["BAAI/bge-reranker-v2-m3"] == Settings().reranker_revision
    assert all(len(revision) == 40 for revision in models.values())


def test_main_ref_points_offline_loaders_at_the_pinned_commit(tmp_path):
    pin_main_ref(tmp_path, "BAAI/bge-reranker-v2-m3", "a" * 40)
    ref = tmp_path / "models--BAAI--bge-reranker-v2-m3" / "refs" / "main"

    assert ref.read_text() == "a" * 40
    pin_main_ref(tmp_path, "BAAI/bge-reranker-v2-m3", "a" * 40)  # idempotent


def test_a_cache_at_another_revision_is_refused_not_overwritten(tmp_path):
    pin_main_ref(tmp_path, "BAAI/bge-reranker-v2-m3", "a" * 40)

    with pytest.raises(ValueError, match="another revision"):
        pin_main_ref(tmp_path, "BAAI/bge-reranker-v2-m3", "b" * 40)
    assert (tmp_path / "models--BAAI--bge-reranker-v2-m3" / "refs" / "main").read_text() == "a" * 40
