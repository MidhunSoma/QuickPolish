import os
import json
import logging
import itertools
from typing import List, Optional
import requests
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("quickpolish-proxy")

app = FastAPI(
    title="QuickPolish Serverless Proxy",
    description="Multi-key rotating proxy for Gemini Flash rewrites",
    version="1.0.0",
)

# Enable CORS for universal desktop client & web compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# GEMINI API KEY POOL & ROTATION
# ---------------------------------------------------------
def load_api_keys() -> List[str]:
    """
    Extracts all Gemini API keys from environment variables.
    Supports comma-separated GEMINI_API_KEYS or individual GEMINI_API_KEY_N vars.
    """
    keys = []
    
    # Check comma-separated variable
    multi_keys = os.environ.get("GEMINI_API_KEYS", "")
    if multi_keys:
        for k in multi_keys.split(","):
            cleaned = k.strip().strip("'\"")
            if cleaned and cleaned not in keys:
                keys.append(cleaned)
                
    # Check individual numbered keys
    for i in range(1, 10):
        key = os.environ.get(f"GEMINI_API_KEY_{i}", "").strip().strip("'\"")
        if key and key not in keys:
            keys.append(key)
            
    # Check fallback single key
    single_key = os.environ.get("GEMINI_API_KEY", "").strip().strip("'\"")
    if single_key and single_key not in keys:
        keys.append(single_key)
        
    return keys

API_KEYS = load_api_keys()
_key_cycle = itertools.cycle(API_KEYS) if API_KEYS else None

def mask_key(key: str) -> str:
    """Masks API key for safe logging (e.g., AIzaSy...7B9x)."""
    if len(key) <= 8:
        return "********"
    return f"{key[:6]}...{key[-4:]}"

# Default Model
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

# ---------------------------------------------------------
# TONE PROMPTS MAPPING
# ---------------------------------------------------------
TONE_INSTRUCTIONS = {
    "Professional": (
        "Rewrite the text to be professional, polished, polite, and business-ready. "
        "Elevate phrasing and clarity while preserving the exact core meaning and intent."
    ),
    "Casual": (
        "Rewrite the text in a friendly, warm, and natural conversational tone. "
        "Make it approachable and easy-going without being overly slangy."
    ),
    "Concise": (
        "Rewrite the text to be ultra-concise, eliminating fluff, filler, and redundancy. "
        "Deliver the core message directly and cleanly in the fewest words possible."
    ),
    "Executive": (
        "Rewrite the text in an executive, authoritative, and strategic tone. "
        "Highlight outcomes and impact with high-level clarity suitable for leadership."
    ),
    "Grammar Only": (
        "Fix only the grammar, spelling, punctuation, and syntax errors. "
        "Keep the original vocabulary, sentence structure, and tone completely intact."
    ),
    "Bullet Points": (
        "Transform the input text into a clean, concise, scannable bullet-pointed list. "
        "Capture every key point, action item, or detail logically."
    ),
}

# ---------------------------------------------------------
# REQUEST / RESPONSE SCHEMAS
# ---------------------------------------------------------
class PolishRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=15000, description="The raw rough text to polish")
    tone: Optional[str] = Field("Professional", description="Desired tone for the rewrite")

class PolishResponse(BaseModel):
    rewritten: str
    tone: str
    model: str
    keys_active: int

# ---------------------------------------------------------
# CORE REWRITE LOGIC WITH AUTOMATIC KEY FAILOVER
# ---------------------------------------------------------
def call_gemini(text: str, tone: str) -> str:
    global API_KEYS, _key_cycle
    
    # Reload keys dynamically if none were initially loaded
    if not API_KEYS:
        API_KEYS = load_api_keys()
        if API_KEYS:
            _key_cycle = itertools.cycle(API_KEYS)
            
    if not API_KEYS or not _key_cycle:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No Gemini API keys configured on proxy server. Please set GEMINI_API_KEYS in environment."
        )

    instruction = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["Professional"])
    
    prompt = (
        f"You are QuickPolish, an expert real-time in-place text editor.\n"
        f"TASK: {instruction}\n\n"
        f"CRITICAL RULES:\n"
        f"1. Output ONLY the polished rewritten text.\n"
        f"2. NEVER include conversational preambles (e.g. 'Here is your rewritten text:'), quotes, or explanations.\n"
        f"3. Preserve all factual details, names, numbers, dates, and URLs accurately.\n\n"
        f"INPUT TEXT:\n"
        f"{text}"
    )

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        }
    }

    last_error = None
    keys_to_try = len(API_KEYS)
    
    # Rotate through available keys if rate-limited or transient failure occurs
    for attempt in range(keys_to_try):
        current_key = next(_key_cycle)
        masked = mask_key(current_key)
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={current_key}"
        
        try:
            logger.info(f"Dispatching rewrite request using key {masked} (attempt {attempt + 1}/{keys_to_try})")
            resp = requests.post(url, json=payload, timeout=12)
            
            # Rate limit or quota exhausted -> failover to next key immediately
            if resp.status_code in (429, 503):
                logger.warning(f"Key {masked} returned {resp.status_code} ({resp.text[:120]}). Rotating to next key...")
                last_error = f"Key {masked} quota exceeded ({resp.status_code})"
                continue
                
            if resp.status_code != 200:
                logger.warning(f"Key {masked} failed with status {resp.status_code}: {resp.text[:120]}")
                last_error = f"API error ({resp.status_code}): {resp.text[:100]}"
                continue
                
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                logger.warning(f"Key {masked} returned no candidates: {data}")
                last_error = "No candidates returned from Gemini"
                continue
                
            rewritten_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            
            # Clean up accidental conversational wrappers or extra whitespace
            rewritten_text = rewritten_text.strip()
            
            # Strip outer quotation marks if the model accidentally wrapped the whole response
            if len(rewritten_text) >= 2 and rewritten_text[0] == '"' and rewritten_text[-1] == '"' and text[0] != '"':
                rewritten_text = rewritten_text[1:-1].strip()

            return rewritten_text

        except requests.RequestException as e:
            logger.warning(f"Request exception with key {masked}: {e}. Retrying next key...")
            last_error = str(e)
            continue

    # If all keys failed
    logger.error("All Gemini API keys in rotation pool exhausted or failed.")
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"All configured Gemini API keys failed or hit quota limits. Last error: {last_error}"
    )

# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------
@app.get("/")
@app.get("/api")
def root_status():
    keys = load_api_keys()
    return {
        "status": "online",
        "service": "QuickPolish Serverless Proxy",
        "keys_loaded": len(keys),
        "model": GEMINI_MODEL,
        "supported_tones": list(TONE_INSTRUCTIONS.keys())
    }

@app.get("/health")
@app.get("/api/health")
def health_check():
    keys = load_api_keys()
    return {
        "status": "healthy",
        "keys_count": len(keys)
    }

@app.post("/polish", response_model=PolishResponse)
@app.post("/api/polish", response_model=PolishResponse)
def polish_endpoint(req: PolishRequest):
    if not req.text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Input text cannot be empty.")
        
    tone = req.tone if req.tone in TONE_INSTRUCTIONS else "Professional"
    polished = call_gemini(req.text, tone)
    
    return PolishResponse(
        rewritten=polished,
        tone=tone,
        model=GEMINI_MODEL,
        keys_active=len(API_KEYS)
    )
