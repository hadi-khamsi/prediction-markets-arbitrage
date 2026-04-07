"""Smart Order Router - finds best execution venue across exchanges."""

from dataclasses import dataclass

from .models import Contract, MatchedPair


@dataclass
class LiquidityParams:
    """Tunable liquidity penalty thresholds."""
    penalty_none: float = 0.03      # No volume data
    penalty_low: float = 0.05       # < $10k
    penalty_medium: float = 0.02    # $10k-$50k
    penalty_high: float = 0.01      # $50k-$100k
    penalty_very_high: float = 0.0  # >= $100k


class SmartOrderRouter:
    """
    Selects optimal execution venues based on:
    - Price (primary)
    - Liquidity (volume-based penalty)
    - Fees

    Score = price + fee + liquidity_penalty (lower = better)
    """

    def __init__(
        self,
        fee_rates: dict[str, float] | None = None,
        liquidity_params: LiquidityParams | None = None,
    ):
        self.fee_rates = fee_rates or {}
        self.liq = liquidity_params or LiquidityParams()

    def select_best_pair(
        self,
        contracts: list[Contract],
        match_type: str = "identical",
        similarity: float = 1.0,
    ) -> MatchedPair | None:
        """
        Given contracts for the same event on multiple exchanges,
        select the best 2 venues for arbitrage.

        Returns a MatchedPair with the two best-scored contracts.
        """
        if len(contracts) < 2:
            return None

        if len(contracts) == 2:
            return MatchedPair(
                contract_a=contracts[0],
                contract_b=contracts[1],
                match_type=match_type,
                similarity=similarity,
            )

        # Score each contract (average of YES and NO scores)
        scored = []
        for c in contracts:
            yes_score = self._score(c, c.yes_price)
            no_score = self._score(c, c.no_price)
            avg_score = (yes_score + no_score) / 2
            scored.append((avg_score, c))

        # Sort by score (lower = better)
        scored.sort(key=lambda x: x[0])

        # Return best 2 as a MatchedPair
        return MatchedPair(
            contract_a=scored[0][1],
            contract_b=scored[1][1],
            match_type=match_type,
            similarity=similarity,
        )

    def _score(self, contract: Contract, price: float) -> float:
        """Score a venue (lower = better)."""
        if price <= 0:
            return float("inf")

        fee_rate = self.fee_rates.get(contract.exchange, 0)
        fee = fee_rate * price

        # Liquidity penalty based on volume
        vol = contract.volume
        if vol is None:
            liq_penalty = self.liq.penalty_none
        elif vol < 10_000:
            liq_penalty = self.liq.penalty_low
        elif vol < 50_000:
            liq_penalty = self.liq.penalty_medium
        elif vol < 100_000:
            liq_penalty = self.liq.penalty_high
        else:
            liq_penalty = self.liq.penalty_very_high

        return price + fee + liq_penalty
