"""Semantic contract matching across prediction market exchanges."""

import logging
import os
import re
import warnings
from datetime import timedelta

os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

for logger_name in ["sentence_transformers", "transformers", "huggingface_hub", "torch", "mlx"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

import numpy as np
from sentence_transformers import SentenceTransformer

from .models import Contract, MatchedPair
from .llm_verifier import LLMVerifier


class ContractMatcher:
    """Finds matching contracts across exchanges using semantic similarity + LLM verification."""

    def __init__(
        self,
        model_name: str,
        min_similarity: float,
        llm_verifier: LLMVerifier,
    ):
        self.min_similarity = min_similarity
        self.model = SentenceTransformer(model_name, device="cpu")
        self.model.eval()
        self.llm = llm_verifier

    def find_matches(
        self,
        contracts_a: list[Contract],
        contracts_b: list[Contract],
    ) -> list[MatchedPair]:
        """Find matching contract pairs between two exchanges."""
        if not contracts_a or not contracts_b:
            return []

        # Normalize titles for embedding
        titles_a = [self._normalize_title(c.title) for c in contracts_a]
        titles_b = [self._normalize_title(c.title) for c in contracts_b]

        # Compute embeddings and similarity
        embeddings_a = self.model.encode(titles_a, convert_to_numpy=True, show_progress_bar=False)
        embeddings_b = self.model.encode(titles_b, convert_to_numpy=True, show_progress_bar=False)
        similarities = self._cosine_similarity(embeddings_a, embeddings_b)

        # Find candidate pairs above similarity threshold
        candidates = []
        for i, contract_a in enumerate(contracts_a):
            for j, contract_b in enumerate(contracts_b):
                sim = similarities[i, j]
                if sim >= self.min_similarity and self._dates_compatible(contract_a, contract_b):
                    candidates.append((contract_a, contract_b, float(sim)))

        # Sort by similarity descending for LLM verification
        candidates.sort(key=lambda x: x[2], reverse=True)

        # LLM verification for match type
        matches = []
        for contract_a, contract_b, sim in candidates:
            match_type = self.llm.classify(contract_a.title, contract_b.title)

            # Skip unrelated or unsure matches
            if match_type in ("unrelated", "unsure"):
                continue

            matches.append(
                MatchedPair(
                    contract_a=contract_a,
                    contract_b=contract_b,
                    match_type=match_type,
                    similarity=sim,
                )
            )

        return matches

    def _normalize_title(self, title: str) -> str:
        """Normalize title for embedding comparison."""
        title = title.lower().strip()
        title = re.sub(r"\s+", " ", title)
        title = re.sub(r"^(will |what |who |when )", "", title)
        title = re.sub(r"\?$", "", title)
        return title

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Compute cosine similarity matrix."""
        a = a / np.linalg.norm(a, axis=1, keepdims=True)
        b = b / np.linalg.norm(b, axis=1, keepdims=True)
        return np.dot(a, b.T)

    def _dates_compatible(self, a: Contract, b: Contract) -> bool:
        """Check if contracts have compatible expiration dates (within 1 day)."""
        if a.end_date is None or b.end_date is None:
            return True
        diff = abs((a.end_date - b.end_date).total_seconds())
        return diff <= timedelta(days=1).total_seconds()
