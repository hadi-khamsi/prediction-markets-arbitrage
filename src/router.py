"""Smart Order Router - selects optimal execution venues across exchanges.

The router scores each venue using three components:
1. COST: The price to execute (lower = better)
2. SPREAD: Bid-ask spread as real-time liquidity measure (lower = better)
3. VOLUME: Historical trading volume as secondary signal (higher = better)

Final score = cost + spread_penalty + volume_penalty
Lower score = better venue for execution.
"""

from dataclasses import dataclass

from .contracts import Contract, MatchedPair


@dataclass
class RouterConfig:
    """Configuration for the smart order router scoring."""
    # Fee rates by exchange
    fee_rates: dict[str, float]

    # Spread-based penalties (real-time liquidity)
    spread_penalty_none: float = 0.02
    spread_penalty_tight: float = 0.00      # < 2%
    spread_penalty_medium: float = 0.01     # 2-5%
    spread_penalty_wide: float = 0.03       # 5-10%
    spread_penalty_very_wide: float = 0.05  # > 10%

    # Volume-based penalties (historical liquidity)
    volume_penalty_none: float = 0.02
    volume_penalty_low: float = 0.03        # < $10k
    volume_penalty_medium: float = 0.01     # $10k-$50k
    volume_penalty_high: float = 0.005      # $50k-$100k
    volume_penalty_very_high: float = 0.0   # >= $100k


class SmartOrderRouter:
    """Routes orders to optimal venues based on cost, spread, and volume."""

    def __init__(self, config: RouterConfig):
        self.config = config

    def select_best_pair(
        self,
        contracts: list[Contract],
        match_type: str = "identical",
        similarity: float = 1.0,
    ) -> MatchedPair | None:
        """Select the best 2 venues from 3+ exchanges for an event.

        When the same event exists on multiple exchanges, this picks
        the two with the best combined score.
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

        # Score each contract and pick best 2
        scored = [(self._score(c), c) for c in contracts]
        scored.sort(key=lambda x: x[0])

        return MatchedPair(
            contract_a=scored[0][1],
            contract_b=scored[1][1],
            match_type=match_type,
            similarity=similarity,
        )

    def _score(self, contract: Contract) -> float:
        """Calculate venue score: cost + spread_penalty + volume_penalty.

        Lower score = better venue.
        """
        # Component 1: Cost (price + fees)
        price = (contract.yes_price + contract.no_price) / 2
        fee_rate = self.config.fee_rates.get(contract.exchange, 0)
        cost = price + (price * fee_rate)

        # Component 2: Spread penalty (real-time liquidity)
        spread_penalty = self._spread_penalty(contract)

        # Component 3: Volume penalty (historical liquidity)
        volume_penalty = self._volume_penalty(contract)

        return cost + spread_penalty + volume_penalty

    def _spread_penalty(self, contract: Contract) -> float:
        """Calculate penalty based on bid-ask spread.

        Spread = ask - bid. Tighter spread = more liquid = lower penalty.
        """
        spread = contract.spread
        if spread is None:
            return self.config.spread_penalty_none

        # Convert to percentage
        spread_pct = spread / contract.yes_price if contract.yes_price > 0 else 0

        if spread_pct < 0.02:
            return self.config.spread_penalty_tight
        elif spread_pct < 0.05:
            return self.config.spread_penalty_medium
        elif spread_pct < 0.10:
            return self.config.spread_penalty_wide
        else:
            return self.config.spread_penalty_very_wide

    def _volume_penalty(self, contract: Contract) -> float:
        """Calculate penalty based on historical volume.

        Higher volume = more liquid = lower penalty.
        """
        vol = contract.volume
        if vol is None:
            return self.config.volume_penalty_none

        if vol < 10_000:
            return self.config.volume_penalty_low
        elif vol < 50_000:
            return self.config.volume_penalty_medium
        elif vol < 100_000:
            return self.config.volume_penalty_high
        else:
            return self.config.volume_penalty_very_high


# Legacy compatibility - keep old interface working
@dataclass
class LiquidityParams:
    """Deprecated: Use RouterConfig instead."""
    penalty_none: float = 0.03
    penalty_low: float = 0.05
    penalty_medium: float = 0.02
    penalty_high: float = 0.01
    penalty_very_high: float = 0.0
