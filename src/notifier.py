"""
notifier.py - send alerts via CallMeBot Facebook Messenger webhook.

API docs: https://www.callmebot.com/blog/free-api-facebook-messenger/

You authorize the bot on FB Messenger (one-time), get an API key, then POST to:
  https://api.callmebot.com/facebook/send.php?apikey=...&text=...

The bot replies through FB Messenger to your account.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

import config

log = logging.getLogger("notifier")


def send(message: str, api_key: str | None = None, timeout: int = 30) -> dict:
    """
    Send a single FB Messenger message via CallMeBot.
    Returns the parsed JSON response (or raises).
    """
    key = api_key or config.CALLMEBOT_API_KEY
    if not key:
        raise RuntimeError("Missing CALLMEBOT_API_KEY")

    # URL-encode the message
    params = urllib.parse.urlencode({
        "apikey": key,
        "text": message,
    })
    url = f"{config.CALLMEBOT_URL}?{params}"

    log.info("POST %s", config.CALLMEBOT_URL)
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw": body}
            log.info("CallMeBot response: %s", parsed)
            return parsed
    except Exception as e:
        log.error("CallMeBot error: %s", e)
        raise


def send_signals_notification(signals_text: str) -> dict:
    """Convenience wrapper that sends the scanner output to FB Messenger."""
    return send(signals_text)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--msg", "-m", required=True, help="Message text to send")
    args = ap.parse_args()
    r = send(args.msg)
    print("Response:", r)
