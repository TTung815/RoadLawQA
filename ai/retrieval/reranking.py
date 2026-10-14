"""Reduce inference padding while preserving the full pairs and their score order."""

from collections.abc import Sequence

from ai.diagnostics import record


class LengthBatchedReranker:
    def __init__(self, model, batch_size: int = 4):
        if not 1 <= batch_size <= 32:
            raise ValueError("reranker batch_size must be between 1 and 32")
        self.model = model
        self.batch_size = batch_size

    def predict(self, pairs: Sequence[Sequence[str]]) -> list[float]:
        if not pairs:
            return []
        # Same tokenizer/truncation limit as CrossEncoder.predict. Keep full
        # source text and parent conditions instead of shortening the input.
        encoded = self.model.tokenizer(
            [p[0] for p in pairs], [p[1] for p in pairs], padding=False,
            truncation="longest_first", max_length=self.model.max_length,
            return_length=True,
        )
        lengths = encoded["length"]
        order = sorted(range(len(pairs)), key=lambda i: lengths[i])
        scores = self.model.predict([pairs[i] for i in order],
                                    batch_size=self.batch_size, show_progress_bar=False)
        restored = [0.0] * len(pairs)
        for i, score in zip(order, scores, strict=True):
            restored[i] = float(score)
        record("rerank_batches", event="selection", batch_size=self.batch_size,
               input_tokens=sum(lengths), padded_tokens=sum(
                   max(lengths[i] for i in order[start:start + self.batch_size]) *
                   len(order[start:start + self.batch_size])
                   for start in range(0, len(order), self.batch_size)))
        return restored
