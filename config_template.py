# Configuration Template for Scopus Research Chatbot
# Copy this file to config.py and fill in your actual credentials

# Scopus API Configuration
# Get these from: https://dev.elsevier.com/
API_KEY = "YOUR_SCOPUS_API_KEY_HERE"
INST_TOKEN = "YOUR_SCOPUS_INST_TOKEN_HERE"

# Optional: Database Configuration
DATABASE_NAME = "scopus_database.db"

# Optional: Model Configuration
EMBEDDING_MODEL = "allenai/specter"  # Default scientific paper embeddings
FALLBACK_MODELS = [
    "allenai/scibert_scivocab_uncased",
    "all-MiniLM-L6-v2"
]

# Optional: Search Configuration
RESULTS_PER_PAGE = 5
MAX_SEARCH_RESULTS = 50

# Optional: API Rate Limiting
API_DELAY_SECONDS = 1.0  # Delay between API calls
MAX_RETRIES = 3
