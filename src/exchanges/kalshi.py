import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from ..contracts import Contract

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
REQUEST_DELAY = 0.3  # seconds between paginated requests


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
                parsed = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                end_date = parsed

            # Kalshi prices are in dollars (0.00-1.00)
            yes_ask = float(market.get("yes_ask_dollars") or 0)
            no_ask = float(market.get("no_ask_dollars") or 0)
            yes_bid = float(market.get("yes_bid_dollars") or 0)
            no_bid = float(market.get("no_bid_dollars") or 0)
            last_price = float(market.get("last_price_dollars") or 0)

            # Fallback if no ask prices
            if yes_ask == 0:
                yes_ask = last_price if last_price else 0.5
            if no_ask == 0:
                no_ask = 1 - yes_ask

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
                yes_price=yes_ask,
                no_price=no_ask,
                end_date=end_date,
                volume=volume_dollars,
                yes_bid=yes_bid if yes_bid > 0 else None,
                no_bid=no_bid if no_bid > 0 else None,
            )
        except (KeyError, TypeError):
            return None
