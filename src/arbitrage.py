import math

from .contracts import MatchedPair, Opportunity


def calculate_fee(exchange: str, price: float, fee_rates: dict[str, float]) -> float:
    """Calculate fee for a given exchange and price."""
    rate = fee_rates.get(exchange, 0.0)
    if rate == 0 or price <= 0 or price >= 1:
        return 0

    if exchange == "kalshi":
        # Kalshi: round_up(rate × price × (1 - price))
        raw_fee = rate * price * (1 - price)
        return math.ceil(raw_fee * 100) / 100
    else:
        # Default: simple percentage
        return rate * price


class ArbitrageCalculator:
    """Calculates arbitrage opportunities from matched contract pairs."""

    def __init__(
        self,
        fee_rates: dict[str, float] | None = None,
        tax_rate: float = 0.0,
        min_profit: float = 0.001,
    ):
        self.fee_rates = fee_rates or {}
        self.tax_rate = tax_rate
        self.min_profit = min_profit

    def find_opportunities(self, matches: list[MatchedPair]) -> list[Opportunity]:
        """Find all profitable arbitrage opportunities from matched pairs."""
        opportunities = []

        for pair in matches:
            opp = self._calculate_opportunity(pair)
            if opp and opp.profit > self.min_profit:
                opportunities.append(opp)

        opportunities.sort(key=lambda o: o.profit, reverse=True)
        return opportunities

    def _calculate_opportunity(self, pair: MatchedPair) -> Opportunity | None:
        """Calculate arbitrage opportunity for a matched pair."""
        a = pair.contract_a
        b = pair.contract_b

        best_opp = None
        best_profit = -float("inf")

        combinations = [
            ("BUY YES", "BUY NO", a.yes_price, b.no_price),
            ("BUY NO", "BUY YES", a.no_price, b.yes_price),
            ("BUY YES", "BUY YES", a.yes_price, b.yes_price),
            ("BUY NO", "BUY NO", a.no_price, b.no_price),
        ]

        for action_a, action_b, price_a, price_b in combinations:
            is_complementary = (
                (action_a != action_b and pair.match_type == "identical")
                or (action_a == action_b and pair.match_type == "opposite")
            )

            if not is_complementary:
                continue

            total_cost = price_a + price_b
            fee_a = calculate_fee(a.exchange, price_a, self.fee_rates)
            fee_b = calculate_fee(b.exchange, price_b, self.fee_rates)
            total_fees = fee_a + fee_b

            tax = total_fees * self.tax_rate if self.tax_rate > 0 else 0
            profit = 1.0 - total_cost - total_fees - tax

            if profit > best_profit:
                best_profit = profit
                best_opp = Opportunity(
                    pair=pair,
                    total_cost=total_cost,
                    fees=total_fees,
                    profit=profit,
                    action_a=action_a,
                    action_b=action_b,
                )

        return best_opp
