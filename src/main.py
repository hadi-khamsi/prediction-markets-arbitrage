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
from .contracts import Contract, MatchedPair
from .router import SmartOrderRouter, RouterConfig


def filter_by_volume(contracts: list[Contract], min_volume: float) -> list[Contract]:
    """Filter contracts by minimum volume. Keeps contracts with unknown volume."""
    if min_volume <= 0:
        return contracts
    return [c for c in contracts if c.volume is None or c.volume >= min_volume]


def dedupe_matches(
    matches: list[MatchedPair],
    router: SmartOrderRouter,
) -> list[MatchedPair]:
    """
    Deduplicate matches when same event exists on 3+ exchanges.
    Uses router to select best 2 venues.
    """
    contract_matches: dict[str, list[MatchedPair]] = {}
    for m in matches:
        key_a = f"{m.contract_a.exchange}:{m.contract_a.id}"
        key_b = f"{m.contract_b.exchange}:{m.contract_b.id}"
        contract_matches.setdefault(key_a, []).append(m)
        contract_matches.setdefault(key_b, []).append(m)

    processed = set()
    final_matches = []

    for m in matches:
        key_a = f"{m.contract_a.exchange}:{m.contract_a.id}"
        key_b = f"{m.contract_b.exchange}:{m.contract_b.id}"
        pair_key = tuple(sorted([key_a, key_b]))

        if pair_key in processed:
            continue

        contracts_by_exchange: dict[str, Contract] = {
            m.contract_a.exchange: m.contract_a,
            m.contract_b.exchange: m.contract_b,
        }

        for other_match in contract_matches.get(key_a, []) + contract_matches.get(key_b, []):
            if other_match == m:
                continue
            for c in [other_match.contract_a, other_match.contract_b]:
                if c.exchange not in contracts_by_exchange:
                    contracts_by_exchange[c.exchange] = c

        contracts = list(contracts_by_exchange.values())

        if len(contracts) == 2:
            final_matches.append(m)
        else:
            best_pair = router.select_best_pair(
                contracts,
                match_type=m.match_type,
                similarity=m.similarity,
            )
            if best_pair:
                final_matches.append(best_pair)

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

    router_config = RouterConfig(
        fee_rates=fee_rates,
        spread_penalty_none=config.SPREAD_PENALTY_NONE,
        spread_penalty_tight=config.SPREAD_PENALTY_TIGHT,
        spread_penalty_medium=config.SPREAD_PENALTY_MEDIUM,
        spread_penalty_wide=config.SPREAD_PENALTY_WIDE,
        spread_penalty_very_wide=config.SPREAD_PENALTY_VERY_WIDE,
        volume_penalty_none=config.VOLUME_PENALTY_NONE,
        volume_penalty_low=config.VOLUME_PENALTY_LOW,
        volume_penalty_medium=config.VOLUME_PENALTY_MEDIUM,
        volume_penalty_high=config.VOLUME_PENALTY_HIGH,
        volume_penalty_very_high=config.VOLUME_PENALTY_VERY_HIGH,
    )

    router = SmartOrderRouter(config=router_config)

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
                kalshi_contracts = filter_by_volume(kalshi_contracts, config.MIN_VOLUME)
            except Exception:
                kalshi_contracts = []
            latencies["kalshi"] = int((time_module.perf_counter() - t0) * 1000)
            exchange_counts["kalshi"] = len(kalshi_contracts)

            t0 = time_module.perf_counter()
            try:
                poly_contracts = polymarket.fetch_markets(max_days=config.MAX_DAYS_OUT)
                poly_contracts = filter_by_volume(poly_contracts, config.MIN_VOLUME)
            except Exception:
                poly_contracts = []
            latencies["polymarket"] = int((time_module.perf_counter() - t0) * 1000)
            exchange_counts["polymarket"] = len(poly_contracts)

            t0 = time_module.perf_counter()
            try:
                # PredictIt has no volume data, skip volume filter for it
                predictit_contracts = predictit.fetch_markets(max_days=config.MAX_DAYS_OUT)
            except Exception:
                predictit_contracts = []
            latencies["predictit"] = int((time_module.perf_counter() - t0) * 1000)
            exchange_counts["predictit"] = len(predictit_contracts)

            # Match all pairwise combinations
            matches_kp = matcher.find_matches(kalshi_contracts, poly_contracts)
            matches_kpi = matcher.find_matches(kalshi_contracts, predictit_contracts)
            matches_ppi = matcher.find_matches(poly_contracts, predictit_contracts)
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
