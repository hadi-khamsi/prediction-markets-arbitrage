import math

from .models import Contract, MatchedPair, Opportunity


def calculate_kalshi_fee(price: float, fee_rate: float = 0.07) -> float:
    """
    Calculate Kalshi taker fee.
    Formula: round_up(fee_rate × price × (1 - price))
    Fee is highest at 50¢, lowest at extremes.
    """
    if price <= 0 or price >= 1:
        return 0
    raw_fee = fee_rate * price * (1 - price)
    # Round up to nearest cent
    return math.ceil(raw_fee * 100) / 100


def calculate_polymarket_fee(price: float, fee_rate: float = 0.01) -> float:
    """
    Calculate Polymarket taker fee.
    Simplified: fee_rate × price
    """
    return fee_rate * price


class ArbitrageCalculator:
    """Calculates arbitrage opportunities from matched contract pairs."""

    def __init__(
        self,
        kalshi_fee_rate: float = 0.07,
        polymarket_fee_rate: float = 0.01,
        tax_rate: float = 0.0,
        min_profit: float = 0.001,
    ):
        self.kalshi_fee_rate = kalshi_fee_rate
        self.polymarket_fee_rate = polymarket_fee_rate
        self.tax_rate = tax_rate
        self.min_profit = min_profit

    def find_opportunities(
        self, matches: list[MatchedPair]
    ) -> list[Opportunity]:
        """Find all profitable arbitrage opportunities from matched pairs."""
        opportunities = []

        for pair in matches:
            opp = self._calculate_opportunity(pair)
            if opp and opp.profit > self.min_profit:
                opportunities.append(opp)

        # Sort by profit descending
        opportunities.sort(key=lambda o: o.profit, reverse=True)
        return opportunities

    def _calculate_opportunity(self, pair: MatchedPair) -> Opportunity | None:
        """Calculate arbitrage opportunity for a matched pair."""
        kalshi = pair.contract_a if pair.contract_a.exchange == "kalshi" else pair.contract_b
        poly = pair.contract_b if pair.contract_b.exchange == "polymarket" else pair.contract_a

        # Try all four combinations and find the most profitable
        best_opp = None
        best_profit = -float("inf")

        combinations = [
            ("BUY YES", "BUY NO", kalshi.yes_price, poly.no_price),
            ("BUY NO", "BUY YES", kalshi.no_price, poly.yes_price),
            ("BUY YES", "BUY YES", kalshi.yes_price, poly.yes_price),
            ("BUY NO", "BUY NO", kalshi.no_price, poly.no_price),
        ]

        for kalshi_action, poly_action, k_price, p_price in combinations:
            # For identical contracts: Y+N or N+Y guarantees payout
            # For opposite contracts: Y+Y or N+N guarantees payout
            is_complementary = (
                (kalshi_action != poly_action and pair.match_type == "identical")
                or (kalshi_action == poly_action and pair.match_type == "opposite")
            )

            if not is_complementary:
                continue

            total_cost = k_price + p_price
            k_fee = calculate_kalshi_fee(k_price, self.kalshi_fee_rate)
            p_fee = calculate_polymarket_fee(p_price, self.polymarket_fee_rate)
            total_fees = k_fee + p_fee

            # Apply tax if configured
            tax = total_fees * self.tax_rate if self.tax_rate > 0 else 0

            profit = 1.0 - total_cost - total_fees - tax

            if profit > best_profit:
                best_profit = profit
                best_opp = Opportunity(
                    pair=pair,
                    total_cost=total_cost,
                    fees=total_fees,
                    profit=profit,
                    kalshi_action=kalshi_action,
                    poly_action=poly_action,
                )

        return best_opp
