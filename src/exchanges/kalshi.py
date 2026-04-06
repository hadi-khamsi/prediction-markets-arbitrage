import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from ..models import Contract

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
REQUEST_DELAY = 0.3  # seconds between paginated requests
MAX_CONTRACTS = 500  # limit total contracts to fetch


class KalshiClient:
    """Client for fetching market data from Kalshi."""

    def __init__(self):
        self.session = requests.Session()
        # Auth is optional for market data reads
        api_key = os.getenv("KALSHI_API_KEY")
        api_secret = os.getenv("KALSHI_API_SECRET")
        if api_key and api_secret:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

    def fetch_markets(self, max_days: int = 14) -> list[Contract]:
        """Fetch markets from events (excludes sports parlays)."""
        contracts = []
        cursor = None
        cutoff_date = datetime.now(timezone.utc) + timedelta(days=max_days)

        while True:
            params = {
                "status": "open",
                "limit": 50,
                "with_nested_markets": "true",
            }
            if cursor:
                params["cursor"] = cursor

            resp = self.session.get(f"{BASE_URL}/events", params=params)
            resp.raise_for_status()
            data = resp.json()

            for event in data.get("events", []):
                for market in event.get("markets", []):
                    contract = self._parse_market(market, event)
                    if contract is None:
                        continue
                    # Skip contracts without end date
                    if contract.end_date is None:
                        continue
                    # Filter by expiration date
                    if contract.end_date > cutoff_date:
                        continue
                    contracts.append(contract)
                    if len(contracts) >= MAX_CONTRACTS:
                        return contracts

            cursor = data.get("cursor")
            if not cursor:
                break
            # Rate limit between pages
            time.sleep(REQUEST_DELAY)

        return contracts

    def _parse_market(self, market: dict, event: dict) -> Optional[Contract]:
        """Parse Kalshi market data into a Contract."""
        try:
            # Parse end date from market or event
            end_date = None
            close_time = market.get("close_time") or event.get("close_time")
            if close_time:
                end_date = datetime.fromisoformat(
                    close_time.replace("Z", "+00:00")
                )

            # Kalshi prices are in dollars (0.00-1.00)
            yes_ask_str = market.get("yes_ask_dollars", "0")
            no_ask_str = market.get("no_ask_dollars", "0")
            last_price_str = market.get("last_price_dollars", "0")

            yes_price = float(yes_ask_str) if yes_ask_str else 0.0
            no_price = float(no_ask_str) if no_ask_str else 0.0

            # If no ask prices, use last price or derive
            if yes_price == 0:
                yes_price = float(last_price_str) if last_price_str else 0.5
            if no_price == 0:
                no_price = 1 - yes_price

            # Build title from event + market subtitle
            event_title = event.get("title", "")
            market_subtitle = market.get("subtitle", "")
            if market_subtitle and market_subtitle != event_title:
                title = f"{event_title}: {market_subtitle}"
            else:
                title = event_title or market.get("ticker", "")

            # Volume in contracts - multiply by ~$0.50 avg price for rough dollar estimate
            volume_contracts = market.get("volume_fp")
            volume_dollars = float(volume_contracts) * 0.5 if volume_contracts else None

            return Contract(
                exchange="kalshi",
                id=market["ticker"],
                title=title,
                yes_price=yes_price,
                no_price=no_price,
                end_date=end_date,
                volume=volume_dollars,
            )
        except (KeyError, TypeError):
            return None
