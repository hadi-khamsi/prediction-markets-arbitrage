"""Configuration for the prediction markets terminal."""

# Data refresh
SCAN_INTERVAL = 15           # seconds between refreshes
MAX_DAYS_OUT = 100           # only show contracts expiring within N days

# Matching
MIN_SIMILARITY = 0.25       # minimum semantic similarity to consider a match

# Arbitrage
MIN_PROFIT = 0.01          # minimum profit ($) to display
KALSHI_FEE_RATE = 0.00      # Kalshi taker fee multiplier
POLYMARKET_FEE_RATE = 0.00  # Polymarket taker fee rate
TAX_RATE = 0.0              # optional tax adjustment (0 = disabled)
