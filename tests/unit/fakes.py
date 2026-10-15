"""Deterministic fakes shared by unit tests: scripted LLM/retriever and legal chunks."""

import json

import pytest

from ai.llm.base import LLMProvider
from ai.retrieval.base import RetrievedChunk, Retriever


class ScriptedProvider(LLMProvider):
    def __init__(self, script, events=None):
        self.script = list(script)
        self.calls = []
        self.events = events if events is not None else []

    async def generate(self, *args, **kwargs):
        pytest.fail("The workflow must use structured generation exclusively")

    async def generate_structured(self, messages, response_schema, temperature=0.1, **kwargs):
        assert temperature == 0.0
        assert kwargs == {}
        assert [message.role for message in messages] == ["system", "user"]
        self.calls.append({
            "schema": response_schema,
            "prompt": messages[0].content,
            "payload": json.loads(messages[1].content),
        })
        self.events.append(response_schema.__name__)
        assert self.script, "Unexpected extra LLM call"
        expected, result = self.script.pop(0)
        assert response_schema is expected
        if isinstance(result, Exception):
            raise result
        # Most fixtures use the flat diagnostic draft contract.
        from ai.agent.answer_generator import GeneratedAnswer, DraftAnswer
        if response_schema is GeneratedAnswer and "answer" not in result:
            result = {"answer": DraftAnswer.model_validate(result).model_dump()}
        return response_schema(**result)


class ScriptedRetriever(Retriever):
    def __init__(self, batches, events=None):
        self.batches = list(batches)
        self.calls = []
        self.events = events if events is not None else []

    async def search(self, query, top_k=5, **kwargs):
        self.calls.append((query, top_k))
        self.events.append("retrieve")
        assert self.batches, "Unexpected extra retrieval attempt"
        result = self.batches.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def chunk(identifier, score=0.5):
    return RetrievedChunk(
        id=identifier, text="Test-only legal passage", enriched_text="Test-only legal context",
        citation=f"Test citation {identifier}", score=score,
        metadata={"law": "Test law", "raw_score": 0.1, "rerank_score": score},
    )


def semantic(count, supported=True, complete=True):
    return {"assessments": [
        {"claim_index": index, "supported": supported,
         "support_state": "positive_support" if supported else "unknown",
         "reason": "Supported by attached source." if supported else "Attached source does not support the claim."}
        for index in range(count)],
        "response_appropriate": supported, "answer_complete": complete, "completeness_reason": "Question coverage checked."}


def legal(identifier, clause='6', point='a', text='Test monetary evidence for the requested car range.',
          head='Phạt tiền đối với người điều khiển xe', law='Test regulation', article='6'):
    return RetrievedChunk(id=identifier, text=text, enriched_text=text,
                          citation=f'{law}: Điều {article}, khoản {clause}, điểm {point}', score=0.8,
                          metadata={'law': law, 'article_no': article, 'clause_no': clause,
                                    'point': point, 'clause_head': head})


def consequence(identifier='points', clause='16', point='b', reference='khoản 6', **kwargs):
    return legal(identifier, clause, point,
                 text=f'Thực hiện hành vi quy định tại {reference} Điều này bị trừ điểm giấy phép lái xe.',
                 head='Ngoài hình thức xử phạt còn bị trừ điểm giấy phép lái xe', **kwargs)


class Lookup:
    def __init__(self, chunks):
        self.chunks, self.calls = chunks, []

    async def fetch(self, law, article):
        self.calls.append((law, article))
        if isinstance(self.chunks, Exception):
            raise self.chunks
        return self.chunks
