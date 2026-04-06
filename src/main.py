#!/usr/bin/env python3
"""Arbitrage Scanner - Monitors Kalshi and Polymarket for arbitrage opportunities."""

import sys
import time

from dotenv import load_dotenv

# Import config from project root
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
import config

from .arbitrage import ArbitrageCalculator
from .dashboard import Dashboard
from .exchanges import KalshiClient, PolymarketClient
from .matcher import ContractMatcher


def main():
    load_dotenv()

    print("Initializing...")
    print("Loading semantic model (first run downloads ~80MB)...")

    kalshi = KalshiClient()
    polymarket = PolymarketClient()
    matcher = ContractMatcher(min_similarity=config.MIN_SIMILARITY)
    calculator = ArbitrageCalculator(
        kalshi_fee_rate=config.KALSHI_FEE_RATE,
        polymarket_fee_rate=config.POLYMARKET_FEE_RATE,
        tax_rate=config.TAX_RATE,
        min_profit=config.MIN_PROFIT,
    )
    dashboard = Dashboard()

    print("Ready.")
    print()

    try:
        while True:
            try:
                kalshi_contracts = kalshi.fetch_markets(max_days=config.MAX_DAYS_OUT)
            except Exception as e:
                print(f"Error fetching Kalshi markets: {e}")
                kalshi_contracts = []

            try:
                poly_contracts = polymarket.fetch_markets(max_days=config.MAX_DAYS_OUT)
            except Exception as e:
                print(f"Error fetching Polymarket markets: {e}")
                poly_contracts = []

            matches = matcher.find_matches(kalshi_contracts, poly_contracts)
            opportunities = calculator.find_opportunities(matches)

            dashboard.render(
                opportunities=opportunities,
                kalshi_count=len(kalshi_contracts),
                poly_count=len(poly_contracts),
                matched_count=len(matches),
            )

            time.sleep(config.SCAN_INTERVAL)

    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)


if __name__ == "__main__":
    main()
