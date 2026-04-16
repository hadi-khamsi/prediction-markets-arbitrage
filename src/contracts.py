from dataclasses import dataclass
from datetime import datetime


@dataclass
class Contract:
    """A prediction market contract from any exchange."""
    exchange: str           # "kalshi", "polymarket", "predictit"
    id: str                 # exchange-specific identifier
    title: str              # human-readable contract title
    yes_price: float        # ask price for YES (cost to buy)
    no_price: float         # ask price for NO (cost to buy)
    end_date: datetime | None = None
    volume: float | None = None
    yes_bid: float | None = None   # bid price for YES (for spread calc)
    no_bid: float | None = None    # bid price for NO (for spread calc)

    @property
    def spread(self) -> float | None:
        """Bid-ask spread as liquidity measure. Lower = more liquid."""
        if self.yes_bid is not None:
            return self.yes_price - self.yes_bid
        return None


@dataclass
class MatchedPair:
    """Two contracts from different exchanges that refer to the same event."""
    contract_a: Contract
    contract_b: Contract
    match_type: str         # "identical" or "opposite"
    similarity: float       # semantic similarity score (0.0-1.0)


@dataclass
class Opportunity:
    """An arbitrage opportunity with calculated profit."""
    pair: MatchedPair
    total_cost: float       # combined cost of both positions
    fees: float             # combined exchange fees
    profit: float           # guaranteed profit after fees
    action_a: str           # "BUY YES" or "BUY NO" for contract_a
    action_b: str           # "BUY YES" or "BUY NO" for contract_b
