"""Helper: find your Telegram chat ID for LEAD_TELEGRAM_CHAT_ID.

Usage:
  1. Create a bot via @BotFather and copy the token.
  2. Send any message to the bot from your Telegram account (or add it to a group
     and send a message there).
  3. Run:
       LEAD_TELEGRAM_BOT_TOKEN=<token> python scripts/get_telegram_chat_id.py
  4. Copy the chat ID printed and paste it into .env as LEAD_TELEGRAM_CHAT_ID.

For groups the chat ID usually starts with -100...
"""

import json
import os
import urllib.request


def main() -> None:
    token = os.getenv("LEAD_TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("ERROR: set LEAD_TELEGRAM_BOT_TOKEN in environment before running.")
        return

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        print(f"ERROR: Telegram request failed — {exc}")
        return

    updates = data.get("result", [])
    if not updates:
        print(
            "No updates found.\n"
            "Send any message to your bot (or in the group where the bot is added) "
            "and run this script again."
        )
        return

    seen: set[int] = set()
    for update in updates:
        for key in ("message", "channel_post", "my_chat_member"):
            msg = update.get(key)
            if not msg:
                continue
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id and chat_id not in seen:
                seen.add(chat_id)
                chat_type = chat.get("type", "?")
                title = chat.get("title") or chat.get("username") or chat.get("first_name") or "?"
                print(f"  chat_id={chat_id}  type={chat_type}  name={title}")

    if not seen:
        print("Updates found but no chat IDs — try sending another message and re-run.")
    else:
        print("\nSet the desired chat_id in .env:")
        print("  LEAD_TELEGRAM_CHAT_ID=<chat_id>")


if __name__ == "__main__":
    main()
