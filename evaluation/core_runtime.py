"""Evaluation dependency wiring: read-only shadow resources and existing V2 agents.

No production dependency factory or legacy module with import side effects is used.
Heavy models/connections are created only by explicit live run, never on import.
"""

from __future__ import annotations

from ai.agent.answer_generator import AnswerGenerator
from ai.agent.citation_verifier import CitationVerifier
from ai.agent.contextualizer import QueryContextualizer
from ai.retrieval.base import RetrievedChunk, Retriever
from ai.retrieval.neighborhood import LegalNeighborhoodExpander
from ai.pipeline.retrieval import LeanRetrievalService
from ai.pipeline.answer import AnswerService
from evaluation.core_schema import Question, RunSettings
from evaluation.legacy_probe import runtime_id
from ingestion.legal_registry import PROJECT_ROOT, read_json
from ai.diagnostics import TRACE


def map_chunk(chunk: dict, score: float = 0.0) -> RetrievedChunk:
    """Map a frozen leaf row (current-law corpus) to the retriever contract."""
    return RetrievedChunk(id=runtime_id(chunk), text=chunk["text"], enriched_text=chunk["enriched_text"],
                          citation=chunk["display_citation"], score=score,
                          metadata={**{k: v for k, v in chunk.items() if k not in {"id", "text", "enriched_text"}},
                                    "processed_id": chunk["id"]})


class CoreRuntime:
    def __init__(self, provider, chunks: list[dict], settings: RunSettings, retriever: Retriever | None = None,
                 client=None):
        self.provider, self.settings, self.retriever, self.client = provider, settings, retriever, client
        self.chunks = {c["id"]: c for c in chunks}

    async def fetch_article(self, law: str, article_no: str):
        if self.retriever is not None and hasattr(self.retriever, "fetch_article"):
            return await self.retriever.fetch_article(law, article_no)
        return [map_chunk(c) for c in self.chunks.values() if c["law"] == law and
                c["article_no"] == article_no]

    async def execute(self, question: Question) -> dict:
        self.last_trace = []
        token = TRACE.set(self.last_trace)
        try:
            return await self._execute(question)
        except Exception as exc:
            from ai.diagnostics import PipelineError
            if isinstance(exc, PipelineError):
                raise
            raise PipelineError(getattr(exc, "pipeline_stage", "runtime"), type(exc).__name__) from exc
        finally:
            TRACE.reset(token)

    async def _execute(self, question: Question) -> dict:
        context = QueryContextualizer(self.provider)
        history = [m.model_dump() for m in question.chat_history]
        if question.mode != "end_to_end":
            raise ValueError("only end-to-end questions are executed")
        if self.retriever is None:
            raise ValueError("end-to-end needs the isolated shadow retriever")
        if self.settings.max_attempts != 1:
            raise ValueError("Lean end-to-end execution requires a new plan with max_attempts=1")
        retrieval = LeanRetrievalService(context, self.retriever,
                    structural_expander=LegalNeighborhoodExpander(
                        self.fetch_article, combination_lookup=getattr(self.retriever, "fetch_combination_rules", None))
                    if self.settings.expansion else None)
        service = AnswerService(retrieval, AnswerGenerator(self.provider), CitationVerifier(self.provider))
        return (await service.answer(question.current_query, history, top_k=self.settings.top_k)).model_dump(mode="json")

    def usage(self) -> list[dict]:
        return list(getattr(self.provider, "observations", []))

    def close(self):
        if self.client is not None:
            self.client.close()


def create_evaluation_provider(settings: RunSettings):
    """Credentials come from the environment; all behavior comes from the locked plan."""
    from ai.llm.factory import create_provider
    from ai.llm.measurement import MeasuredProvider
    from configs.settings import LLMSettings
    credentials = LLMSettings(llm_provider=settings.provider, llm_model_name=settings.model,
                              openai_reasoning_effort=settings.reasoning_effort or "medium",
                              openai_max_output_tokens=settings.max_output_tokens or 16384,
                              llm_request_timeout_seconds=settings.request_timeout_seconds,
                              llm_max_transient_retries=settings.max_transient_retries)
    if settings.provider == "openai" and not (credentials.openai_api_key or "").strip():
        raise ValueError("OPENAI_API_KEY is not configured")
    if settings.provider == "gemini" and not credentials.gemini_api_keys:
        raise ValueError("GEMINI_API_KEY is not configured")
    return MeasuredProvider(create_provider(credentials))


def create_live_runtime(settings: RunSettings, *, needs_retrieval: bool = True) -> CoreRuntime:
    from ai.retrieval.runtime import load_retriever
    from evaluation.current_law_snapshot import DEFAULT_SNAPSHOT_MANIFEST, verify_frozen_snapshot

    verify_frozen_snapshot()
    snapshot = read_json(DEFAULT_SNAPSHOT_MANIFEST)
    chunks = read_json(PROJECT_ROOT / snapshot["processed_corpus"]["path"])["chunks"]
    provider = create_evaluation_provider(settings)
    if not needs_retrieval:
        return CoreRuntime(provider, chunks, settings)
    retriever, client = load_retriever(settings)
    return CoreRuntime(provider, chunks, settings, retriever, client)
