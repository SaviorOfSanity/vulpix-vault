"""
Multi-channel alert dispatcher for Phase 2 eBay Auction Radar.
Supports Gotify (self-hosted), Discord Webhooks, and ntfy with zero extra dependencies.
Reads config from SQLite app_settings first, falling back seamlessly to .env variables.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

from backend.db import get_setting


def get_alert_config(db_path: Optional[str] = None) -> Dict[str, str]:
    """Resolves notification channel settings from app_settings -> env vars."""
    return {
        "gotify_url": (get_setting("gotify_url", "", db_path) or os.getenv("GOTIFY_URL", "")).strip().rstrip("/"),
        "gotify_token": (get_setting("gotify_token", "", db_path) or os.getenv("GOTIFY_APP_TOKEN", "")).strip(),
        "discord_webhook_url": (get_setting("discord_webhook_url", "", db_path) or os.getenv("DISCORD_WEBHOOK_URL", "")).strip(),
        "ntfy_url": (get_setting("ntfy_url", "", db_path) or os.getenv("NTFY_URL", "")).strip(),
    }


async def send_alert(
    title: str,
    message: str,
    url: str = "",
    image_url: str = "",
    priority: int = 7,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Dispatches an alert to all configured channels (Gotify, Discord, ntfy)."""
    cfg = get_alert_config(db_path)
    results: Dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        # 1. Gotify
        if cfg["gotify_url"] and cfg["gotify_token"]:
            try:
                gotify_endpoint = f"{cfg['gotify_url']}/message"
                payload: Dict[str, Any] = {
                    "title": title,
                    "message": f"{message}\n\n{url}".strip() if url else message,
                    "priority": priority,
                }
                if url:
                    payload["extras"] = {"client::notification": {"click": {"url": url}}}
                resp = await client.post(
                    gotify_endpoint,
                    params={"token": cfg["gotify_token"]},
                    json=payload,
                )
                results["gotify"] = {
                    "ok": resp.status_code < 300,
                    "status": resp.status_code,
                    "detail": "Sent" if resp.status_code < 300 else resp.text[:160],
                }
            except Exception as exc:
                results["gotify"] = {"ok": False, "detail": str(exc)}

        # 2. Discord Webhook
        if cfg["discord_webhook_url"]:
            try:
                color = 0x10B981 if "SNIPE" in title.upper() else (0xEF4444 if "ENDING" in title.upper() else 0xF59E0B)
                embed: Dict[str, Any] = {
                    "title": title[:250],
                    "description": message[:2000],
                    "color": color,
                }
                if url:
                    embed["url"] = url
                if image_url and image_url.startswith("http"):
                    embed["thumbnail"] = {"url": image_url}
                resp = await client.post(
                    cfg["discord_webhook_url"],
                    json={"username": "Vulpix Vault Radar", "embeds": [embed]},
                )
                results["discord"] = {
                    "ok": resp.status_code < 300,
                    "status": resp.status_code,
                    "detail": "Sent" if resp.status_code < 300 else resp.text[:160],
                }
            except Exception as exc:
                results["discord"] = {"ok": False, "detail": str(exc)}

        # 3. ntfy
        if cfg["ntfy_url"]:
            try:
                headers = {
                    "Title": title[:120],
                    "Priority": "high" if priority >= 7 else "default",
                    "Tags": "fox_face,rotating_light",
                }
                if url:
                    headers["Click"] = url
                resp = await client.post(cfg["ntfy_url"], content=message.encode("utf-8"), headers=headers)
                results["ntfy"] = {
                    "ok": resp.status_code < 300,
                    "status": resp.status_code,
                    "detail": "Sent" if resp.status_code < 300 else resp.text[:160],
                }
            except Exception as exc:
                results["ntfy"] = {"ok": False, "detail": str(exc)}

    if not results:
        return {"sent": False, "channels": {}, "message": "No alert channel configured (Gotify, Discord, or ntfy)."}

    any_ok = any(ch.get("ok") for ch in results.values())
    return {
        "sent": any_ok,
        "channels": results,
        "message": "Alert delivered!" if any_ok else "All configured alert channels failed.",
    }
