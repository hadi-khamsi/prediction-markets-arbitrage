import logging
import os
import re
import warnings
from datetime import timedelta

# Suppress all noisy warnings from ML libraries before importing them
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

# Silence logging from various ML libraries
for logger_name in [
    "sentence_transformers",
    "transformers",
    "huggingface_hub",
    "torch",
    "mlx",
]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

import numpy as np
from sentence_transformers import SentenceTransformer

from .models import Contract, MatchedPair


class ContractMatcher:
    """Finds matching contracts across exchanges using semantic similarity."""

    def __init__(self, model_name: str, min_similarity: float = 0.50):
        self.min_similarity = min_similarity
        self.model = SentenceTransformer(model_name, device="cpu")
        self.model.eval()

    def find_matches(
        self,
        contracts_a: list[Contract],
        contracts_b: list[Contract],
    ) -> list[MatchedPair]:
        """Find all matching contract pairs between two exchanges."""
        if not contracts_a or not contracts_b:
            return []

        # Get titles for embedding
        titles_a = [self._normalize_title(c.title) for c in contracts_a]
        titles_b = [self._normalize_title(c.title) for c in contracts_b]

        # Compute embeddings
        embeddings_a = self.model.encode(titles_a, convert_to_numpy=True, show_progress_bar=False)
        embeddings_b = self.model.encode(titles_b, convert_to_numpy=True, show_progress_bar=False)

        # Compute cosine similarity matrix
        similarities = self._cosine_similarity(embeddings_a, embeddings_b)

        matches = []
        for i, contract_a in enumerate(contracts_a):
            for j, contract_b in enumerate(contracts_b):
                similarity = similarities[i, j]

                if similarity < self.min_similarity:
                    continue

                # Check if dates are compatible (within 1 day of each other)
                if not self._dates_compatible(contract_a, contract_b):
                    continue

                # Determine if contracts are identical or opposite
                match_type = self._determine_match_type(
                    contract_a.title, contract_b.title
                )

                matches.append(
                    MatchedPair(
                        contract_a=contract_a,
                        contract_b=contract_b,
                        match_type=match_type,
                        similarity=float(similarity),
                    )
                )

        # Sort by similarity descending
        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches

    def _normalize_title(self, title: str) -> str:
        """Normalize contract title for better matching."""
        title = title.lower().strip()
        title = re.sub(r"\s+", " ", title)
        title = re.sub(r"^(will |what |who |when )", "", title)
        title = re.sub(r"\?$", "", title)
        return title

    def _cosine_similarity(
        self, embeddings_a: np.ndarray, embeddings_b: np.ndarray
    ) -> np.ndarray:
        """Compute cosine similarity between two sets of embeddings."""
        norms_a = np.linalg.norm(embeddings_a, axis=1, keepdims=True)
        norms_b = np.linalg.norm(embeddings_b, axis=1, keepdims=True)
        embeddings_a = embeddings_a / norms_a
        embeddings_b = embeddings_b / norms_b
        return np.dot(embeddings_a, embeddings_b.T)

    def _dates_compatible(self, a: Contract, b: Contract) -> bool:
        """Check if two contracts have compatible expiration dates."""
        if a.end_date is None or b.end_date is None:
            return True
        diff = abs((a.end_date - b.end_date).total_seconds())
        return diff <= timedelta(days=1).total_seconds()

    def _determine_match_type(self, title_a: str, title_b: str) -> str:
        """Determine if contracts are identical or opposite."""
        title_a = title_a.lower()
        title_b = title_b.lower()

        negations = [" not ", " won't ", " will not ", " no ", " doesn't ", " does not "]
        a_negated = any(neg in f" {title_a} " for neg in negations)
        b_negated = any(neg in f" {title_b} " for neg in negations)

        if a_negated != b_negated:
            return "opposite"
        return "identical"
