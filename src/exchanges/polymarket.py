import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from ..contracts import Contract

GAMMA_URL = "https://gamma-api.polymarket.com"
REQUEST_DELAY = 0.2  # seconds between paginated requests


class PolymarketClient:
    """Client for fetching market data from Polymarket."""

    def __init__(self):
        self.session = requests.Session()
        # Auth is optional for market data reads
        api_key = os.getenv("POLYMARKET_API_KEY")
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

    def fetch_markets(self, max_days: int = 14) -> list[Contract]:
        """Fetch all active markets expiring within max_days."""
        contracts = []
        cutoff_date = datetime.now(timezone.utc) + timedelta(days=max_days)
        offset = 0
        limit = 100

        while True:
            params = {
                "active": "true",
                "closed": "false",
                "limit": limit,
                "offset": offset,
            }

            resp = self.session.get(f"{GAMMA_URL}/markets", params=params)
            resp.raise_for_status()
            markets = resp.json()

            if not markets:
                break

            for market in markets:
                contract = self._parse_market(market)
                if contract is None:
                    continue
                # Skip contracts without end date (can't verify timing)
                if contract.end_date is None:
                    continue
                # Filter by expiration date
                if contract.end_date > cutoff_date:
                    continue
                contracts.append(contract)

            offset += limit
            if len(markets) < limit:
                break
            # Rate limit between pages
            time.sleep(REQUEST_DELAY)

        return contracts

    def _parse_market(self, market: dict) -> Optional[Contract]:
        """Parse Polymarket market data into a Contract."""
        try:
            # Parse end date
            end_date = None
            end_date_str = market.get("endDate") or market.get("end_date_iso")
            if end_date_str:
                parsed = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                end_date = parsed

            # Get prices from outcome prices or best bid/ask
            # Polymarket prices are already 0.00-1.00
            outcomes = market.get("outcomePrices", "[]")
            if isinstance(outcomes, str):
                import json
                outcomes = json.loads(outcomes)

            if outcomes and len(outcomes) >= 2:
                yes_price = float(outcomes[0])
                no_price = float(outcomes[1])
            else:
                # Try getting from tokens array
                tokens = market.get("tokens", [])
                if tokens and len(tokens) >= 2:
                    yes_price = float(tokens[0].get("price", 0.5))
                    no_price = float(tokens[1].get("price", 0.5))
                else:
                    yes_price = 0.5
                    no_price = 0.5

            # Parse volume as float (API returns string)
            volume = None
            raw_volume = market.get("volume")
            if raw_volume is not None:
                try:
                    volume = float(raw_volume)
                except (ValueError, TypeError):
                    pass

            # Bid/ask for spread calculation
            best_bid = market.get("bestBid")
            best_ask = market.get("bestAsk")
            yes_bid = float(best_bid) if best_bid else None

            return Contract(
                exchange="polymarket",
                id=market.get("conditionId") or market.get("id", ""),
                title=market.get("question", market.get("title", "")),
                yes_price=float(best_ask) if best_ask else yes_price,
                no_price=no_price,
                end_date=end_date,
                volume=volume,
                yes_bid=yes_bid,
            )
        except (KeyError, TypeError, ValueError):
            return None
