"""Configuration for the arbitrage scanner terminal."""

# Data refresh
SCAN_INTERVAL = 15           # seconds between refreshes
MAX_DAYS_OUT = 100           # only show contracts expiring within N days

# Matching
SEMANTIC_MODEL = "all-MiniLM-L6-v2"  # sentence-transformers model for embedding
MIN_SIMILARITY = 0.25                 # minimum semantic similarity to consider a match

# LLM Verification (Ollama)
LLM_MODEL = "llama3.2:latest"         # ollama model for match classification
OLLAMA_URL = "http://localhost:11434" # ollama server address

# Arbitrage
MIN_PROFIT = 0.01          # minimum profit ($) to display
TAX_RATE = 0.0              # optional tax adjustment (0 = disabled)

# Exchange fees (set to 0 to ignore fees in calculations)
KALSHI_FEE_RATE = 0.00
POLYMARKET_FEE_RATE = 0.00
PREDICTIT_FEE_RATE = 0.00   # PredictIt has 10% profit fee + 5% withdrawal, but complex to model

# Display
MAX_DISPLAY_ROWS = 10       # max opportunities to show (0 = unlimited)
CONTRACT_TITLE_WIDTH = 40   # character width for contract title columns (text wraps if longer)

# Smart Order Router - venue scoring: score = price + fee + liquidity_penalty
# Lower score = better venue. Tune these based on your risk tolerance.
LIQUIDITY_PENALTY_NONE = 0.03      # No volume data available
LIQUIDITY_PENALTY_LOW = 0.05       # Volume < $10k (high slippage risk)
LIQUIDITY_PENALTY_MEDIUM = 0.02    # Volume $10k-$50k
LIQUIDITY_PENALTY_HIGH = 0.01      # Volume $50k-$100k
LIQUIDITY_PENALTY_VERY_HIGH = 0.0  # Volume >= $100k (negligible slippage)
