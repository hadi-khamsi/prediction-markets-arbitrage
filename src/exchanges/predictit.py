"""Client for fetching market data from PredictIt."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from ..contracts import Contract

API_URL = "https://www.predictit.org/api/marketdata/all"


class PredictItClient:
    """Client for fetching market data from PredictIt."""

    def __init__(self):
        self.session = requests.Session()

    def fetch_markets(self, max_days: int = 14) -> list[Contract]:
        """Fetch all active markets expiring within max_days."""
        resp = self.session.get(API_URL)
        resp.raise_for_status()
        data = resp.json()

        contracts = []
        cutoff_date = datetime.now(timezone.utc) + timedelta(days=max_days)

        for market in data.get("markets", []):
            for pi_contract in market.get("contracts", []):
                contract = self._parse_contract(pi_contract, market)
                if contract is None:
                    continue
                if contract.end_date and contract.end_date > cutoff_date:
                    continue
                contracts.append(contract)

        return contracts

    def _parse_contract(self, contract: dict, market: dict) -> Optional[Contract]:
        """Parse PredictIt contract data into a Contract."""
        try:
            # Parse end date
            end_date = None
            end_date_str = contract.get("dateEnd") or market.get("dateEnd")
            if end_date_str and end_date_str not in ("N/A", "NA", "n/a", "na"):
                parsed = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                end_date = parsed

            # PredictIt has bid/ask as buy/sell costs
            yes_ask = contract.get("bestBuyYesCost")  # cost to buy YES
            yes_bid = contract.get("bestSellYesCost")  # price to sell YES
            no_ask = contract.get("bestBuyNoCost")    # cost to buy NO
            last_price = contract.get("lastTradePrice")

            # Convert to float, fallback to last price
            yes_price = float(yes_ask) if yes_ask else (float(last_price) if last_price else 0.5)
            no_price = float(no_ask) if no_ask else (1 - yes_price)
            yes_bid_val = float(yes_bid) if yes_bid else None

            # Build title: market name + contract name if different
            market_name = market.get("name", "")
            contract_name = contract.get("name", "")
            if contract_name and contract_name != market_name:
                title = f"{market_name}: {contract_name}"
            else:
                title = market_name or contract_name

            return Contract(
                exchange="predictit",
                id=str(contract.get("id", "")),
                title=title,
                yes_price=yes_price,
                no_price=no_price,
                end_date=end_date,
                volume=None,  # PredictIt API doesn't expose volume
                yes_bid=yes_bid_val,
            )
        except (KeyError, TypeError, ValueError):
            return None
