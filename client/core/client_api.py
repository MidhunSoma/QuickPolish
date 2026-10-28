"""
HTTP client for QuickPolish Desktop Client.
Communicates with the Vercel Serverless Proxy backend.
"""

import logging
from typing import Tuple, Optional
import requests
from .config import config

logger = logging.getLogger("quickpolish.api")

def polish_text(
    text: str,
    tone: Optional[str] = None,
    proxy_url: Optional[str] = None,
    timeout: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Calls the Vercel proxy backend to polish the given text.

    Returns:
        (success: bool, polished_text_or_error_message: str)
    """
    base_url = (proxy_url or config.proxy_url).rstrip("/")
    selected_tone = tone or config.tone
    timeout_sec = timeout or int(config.get("request_timeout_sec", 12))

    payload = {
        "text": text,
        "tone": selected_tone
    }

    # Potential endpoints supported by Vercel rewrite config
    endpoints = [
        f"{base_url}/api/polish",
        f"{base_url}/polish",
    ]

    last_error = ""

    for url in endpoints:
        try:
            logger.info(f"Sending polish request to {url} (Tone: {selected_tone}, length: {len(text)})")
            resp = requests.post(url, json=payload, timeout=timeout_sec)

            if resp.status_code == 200:
                data = resp.json()
                rewritten = data.get("rewritten", "").strip()
                if rewritten:
                    logger.info("Successfully received polished text from proxy.")
                    return True, rewritten
                else:
                    last_error = "Server returned empty rewrite."
                    continue

            elif resp.status_code == 404:
                # Try next endpoint candidate
                last_error = f"Endpoint 404 on {url}"
                continue

            elif resp.status_code == 429:
                err_detail = "Rate limit reached. Please check your Gemini API keys."
                try:
                    err_detail = resp.json().get("detail", err_detail)
                except Exception:
                    pass
                return False, f"Quota Exceeded: {err_detail}"

            else:
                err_msg = f"Proxy error {resp.status_code}"
                try:
                    err_msg = resp.json().get("detail", err_msg)
                except Exception:
                    err_msg = resp.text[:120]
                return False, err_msg

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout calling {url}")
            last_error = "Request timed out. The server or AI model is taking too long."
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error reaching {url}")
            last_error = f"Could not connect to proxy at {base_url}. Please verify URL or internet connection."
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling {url}: {e}")
            last_error = f"Network error: {str(e)}"

    return False, last_error or "Failed to reach QuickPolish proxy backend."

def test_connection(proxy_url: Optional[str] = None) -> Tuple[bool, str]:
    """
    Tests connectivity to the proxy backend health endpoint.
    """
    base_url = (proxy_url or config.proxy_url).rstrip("/")
    try:
        resp = requests.get(f"{base_url}/api", timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            keys_cnt = data.get("keys_loaded", "Unknown")
            model = data.get("model", "Gemini")
            return True, f"Connected to {base_url} (Keys: {keys_cnt}, Model: {model})"
        return False, f"Server responded with status {resp.status_code}"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"
