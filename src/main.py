#!/usr/bin/env python3
"""Arbitrage Scanner - Monitors prediction markets for arbitrage opportunities."""

import sys
import time as time_module

from dotenv import load_dotenv

# Import config from project root
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
import config

from .arbitrage import ArbitrageCalculator
from .dashboard import Dashboard
from .exchanges import KalshiClient, PolymarketClient, PredictItClient
from .llm_verifier import LLMVerifier
from .matcher import ContractMatcher
from .models import Contract, MatchedPair
from .router import SmartOrderRouter, LiquidityParams


def dedupe_matches(
    matches: list[MatchedPair],
    router: SmartOrderRouter,
) -> list[MatchedPair]:
    """
    Deduplicate matches when same event exists on 3+ exchanges.
    Uses router to select best 2 venues.
    """
    # Build graph: contract_id -> list of matches containing it
    contract_matches: dict[str, list[MatchedPair]] = {}
    for m in matches:
        key_a = f"{m.contract_a.exchange}:{m.contract_a.id}"
        key_b = f"{m.contract_b.exchange}:{m.contract_b.id}"
        contract_matches.setdefault(key_a, []).append(m)
        contract_matches.setdefault(key_b, []).append(m)

    # Find triangles (3-way matches) and collect all contracts for same event
    processed = set()
    final_matches = []

    for m in matches:
        key_a = f"{m.contract_a.exchange}:{m.contract_a.id}"
        key_b = f"{m.contract_b.exchange}:{m.contract_b.id}"
        pair_key = tuple(sorted([key_a, key_b]))

        if pair_key in processed:
            continue

        # Collect all contracts connected to this match
        contracts_by_exchange: dict[str, Contract] = {
            m.contract_a.exchange: m.contract_a,
            m.contract_b.exchange: m.contract_b,
        }

        # Check if there's a third exchange connected
        for other_match in contract_matches.get(key_a, []) + contract_matches.get(key_b, []):
            if other_match == m:
                continue
            for c in [other_match.contract_a, other_match.contract_b]:
                if c.exchange not in contracts_by_exchange:
                    contracts_by_exchange[c.exchange] = c

        contracts = list(contracts_by_exchange.values())

        if len(contracts) == 2:
            # Only 2 exchanges, use as-is
            final_matches.append(m)
        else:
            # 3+ exchanges, use router to pick best 2
            best_pair = router.select_best_pair(
                contracts,
                match_type=m.match_type,
                similarity=m.similarity,
            )
            if best_pair:
                final_matches.append(best_pair)

        # Mark all pairs in this cluster as processed
        for c1 in contracts:
            for c2 in contracts:
                if c1.exchange != c2.exchange:
                    k1 = f"{c1.exchange}:{c1.id}"
                    k2 = f"{c2.exchange}:{c2.id}"
                    processed.add(tuple(sorted([k1, k2])))

    return final_matches


def main():
    load_dotenv()

    print("Initializing...")
    print(f"Semantic model: {config.SEMANTIC_MODEL}")
    print(f"LLM model: {config.LLM_MODEL}")

    llm_verifier = LLMVerifier(
        model=config.LLM_MODEL,
        ollama_url=config.OLLAMA_URL,
    )

    kalshi = KalshiClient()
    polymarket = PolymarketClient()
    predictit = PredictItClient()

    matcher = ContractMatcher(
        model_name=config.SEMANTIC_MODEL,
        min_similarity=config.MIN_SIMILARITY,
        llm_verifier=llm_verifier,
    )

    fee_rates = {
        "kalshi": config.KALSHI_FEE_RATE,
        "polymarket": config.POLYMARKET_FEE_RATE,
        "predictit": config.PREDICTIT_FEE_RATE,
    }

    liq_params = LiquidityParams(
        penalty_none=config.LIQUIDITY_PENALTY_NONE,
        penalty_low=config.LIQUIDITY_PENALTY_LOW,
        penalty_medium=config.LIQUIDITY_PENALTY_MEDIUM,
        penalty_high=config.LIQUIDITY_PENALTY_HIGH,
        penalty_very_high=config.LIQUIDITY_PENALTY_VERY_HIGH,
    )

    router = SmartOrderRouter(fee_rates=fee_rates, liquidity_params=liq_params)

    calculator = ArbitrageCalculator(
        fee_rates=fee_rates,
        tax_rate=config.TAX_RATE,
        min_profit=config.MIN_PROFIT,
    )

    dashboard = Dashboard(
        max_rows=config.MAX_DISPLAY_ROWS,
        title_width=config.CONTRACT_TITLE_WIDTH,
    )

    print("Ready.")
    print()

    try:
        while True:
            # Fetch from all exchanges with latency tracking
            exchange_counts = {}
            latencies = {}

            t0 = time_module.perf_counter()
            try:
                kalshi_contracts = kalshi.fetch_markets(max_days=config.MAX_DAYS_OUT)
            except Exception as e:
                print(f"Error fetching Kalshi: {e}")
                kalshi_contracts = []
            latencies["kalshi"] = int((time_module.perf_counter() - t0) * 1000)
            exchange_counts["kalshi"] = len(kalshi_contracts)

            t0 = time_module.perf_counter()
            try:
                poly_contracts = polymarket.fetch_markets(max_days=config.MAX_DAYS_OUT)
            except Exception as e:
                print(f"Error fetching Polymarket: {e}")
                poly_contracts = []
            latencies["polymarket"] = int((time_module.perf_counter() - t0) * 1000)
            exchange_counts["polymarket"] = len(poly_contracts)

            t0 = time_module.perf_counter()
            try:
                pi_contracts = predictit.fetch_markets(max_days=config.MAX_DAYS_OUT)
            except Exception as e:
                print(f"Error fetching PredictIt: {e}")
                pi_contracts = []
            latencies["predictit"] = int((time_module.perf_counter() - t0) * 1000)
            exchange_counts["predictit"] = len(pi_contracts)

            # Match all pairwise combinations
            matches_kp = matcher.find_matches(kalshi_contracts, poly_contracts)
            matches_kpi = matcher.find_matches(kalshi_contracts, pi_contracts)
            matches_ppi = matcher.find_matches(poly_contracts, pi_contracts)
            all_matches = matches_kp + matches_kpi + matches_ppi

            # Dedupe: when same event is on 3 exchanges, router picks best 2
            deduped = dedupe_matches(all_matches, router)

            opportunities = calculator.find_opportunities(deduped)

            dashboard.render(
                opportunities=opportunities,
                exchange_counts=exchange_counts,
                matched_count=len(deduped),
                latencies=latencies,
            )

            time_module.sleep(config.SCAN_INTERVAL)

    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)


if __name__ == "__main__":
    main()
