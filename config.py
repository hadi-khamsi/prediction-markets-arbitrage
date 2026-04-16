"""Configuration for the arbitrage scanner terminal."""

# Data refresh
SCAN_INTERVAL = 30           # seconds between refreshes
MAX_DAYS_OUT = 90             # only show contracts expiring within N days

# Matching
SEMANTIC_MODEL = "all-MiniLM-L6-v2"  # sentence-transformers model for embedding
MIN_SIMILARITY = 0.65                 # minimum semantic similarity to consider a match

# LLM Verification (Ollama)
LLM_MODEL = "llama3.2:latest"         # ollama model for match classification
OLLAMA_URL = "http://localhost:11434" # ollama server address

# Filtering
MIN_VOLUME = 10000     # minimum volume ($) to consider a contract (0 = no filter)

# Arbitrage
MIN_PROFIT = 0.001          # minimum profit ($) to display
TAX_RATE = 0.0              # optional tax adjustment (0 = disabled)

# Exchange fees (set to 0 to ignore fees in calculations)
KALSHI_FEE_RATE = 0.00
POLYMARKET_FEE_RATE = 0.00
PREDICTIT_FEE_RATE = 0.10   # PredictIt has 10% profit fee

# Display
MAX_DISPLAY_ROWS = 10       # max opportunities to show (0 = unlimited)
CONTRACT_TITLE_WIDTH = 40   # character width for contract title columns (text wraps if longer)

# Smart Order Router - venue scoring: score = cost + spread_penalty + volume_penalty
# Lower score = better venue.

# Spread penalties (bid-ask spread as liquidity measure)
SPREAD_PENALTY_NONE = 0.02    # No spread data available
SPREAD_PENALTY_TIGHT = 0.00   # Spread < 2% (very liquid)
SPREAD_PENALTY_MEDIUM = 0.01  # Spread 2-5%
SPREAD_PENALTY_WIDE = 0.03    # Spread 5-10%
SPREAD_PENALTY_VERY_WIDE = 0.05  # Spread > 10% (illiquid)

# Volume penalties (historical volume as secondary signal)
VOLUME_PENALTY_NONE = 0.02    # No volume data (e.g., PredictIt)
VOLUME_PENALTY_LOW = 0.03     # Volume < $10k
VOLUME_PENALTY_MEDIUM = 0.01  # Volume $10k-$50k
VOLUME_PENALTY_HIGH = 0.005   # Volume $50k-$100k
VOLUME_PENALTY_VERY_HIGH = 0.0  # Volume >= $100k
