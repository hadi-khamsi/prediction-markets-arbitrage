from dataclasses import dataclass
from datetime import datetime


@dataclass
class Contract:
    """A prediction market contract from any exchange."""
    exchange: str           # "kalshi" or "polymarket"
    id: str                 # exchange-specific identifier
    title: str              # human-readable contract title
    yes_price: float        # price for YES outcome (0.00-1.00)
    no_price: float         # price for NO outcome (0.00-1.00)
    end_date: datetime | None = None
    volume: float | None = None


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
    kalshi_action: str      # "BUY YES" or "BUY NO"
    poly_action: str        # "BUY YES" or "BUY NO"
