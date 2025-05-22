from datetime import datetime
import requests
import json
import os
import pickle
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ==== КОНФИГ ====
API_KEY = "sk_91b455debc341646af393b6582573e06c70458ce8c0e51d4"
AGENT_ID = "Ett5Z2WymqkwilmMtCCYJ"
DOC_ID = "1iFo9n49wVAhYfdHQUVBzypcm-SzuyY0DCqqpt6Ko4fM4"
LAST_RUN_FILE = "last_run.txt"
TOKEN_PICKLE = "token.pickle"
# ================

def load_last_run():
    return open(LAST_RUN_FILE).read().strip() if os.path.exists(LAST_RUN_FILE) else "1970-01-01T00:00:00Z"

def save_last_run(ts):
    with open(LAST_RUN_FILE, "w") as f:
        f.write(ts)

def fetch_calls():
    url = "https://api.elevenlabs.io/v1/calls"
    headers = {"xi-api-key": API_KEY}
    calls = []
    while url:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        calls.extend(data.get("conversations", []))
        url = data.get("next")
    return calls

def get_docs_service():
    with open(TOKEN_PICKLE, "rb") as token:
        creds = pickle.load(token)
    return build("docs", "v1", credentials=creds)

def format_call_block(call):
    timestamp = call["createdAt"]
    summary = call.get("summary", "No summary.")
    messages = call.get("messages", [])
    block = [f"=== Call at {timestamp} ===", f"Summary:\n{summary}\n"]
    for msg in messages:
        t = msg.get("timestamp", "[time]")
        role = msg.get("role", "").upper()
        text = msg.get("message", "").strip()
        block.append(f"[{t}] {role}: {text}")
    block.append("______________________________________________________________\n")
    return "\n".join(block)

def main():
    last_run = load_last_run()
    print(f"⏱️ Last run: {last_run}")
    all_calls = fetch_calls()

    new_calls = [c for c in all_calls if c["createdAt"] > last_run]
    print(f"🔔 New calls: {len(new_calls)}")

    if not new_calls:
        print("Нет новых звонков.")
        return

    new_calls.sort(key=lambda x: x["createdAt"], reverse=True)
    content = "\n".join(format_call_block(c) for c in new_calls)

    service = get_docs_service()
    requests_body = [{
        "insertText": {
            "location": {"index": 1},
            "text": content + "\n"
        }
    }]
    service.documents().batchUpdate(documentId=DOC_ID, body={"requests": requests_body}).execute()
    print("✅ Calls inserted.")

    latest_ts = max(c["createdAt"] for c in new_calls)
    save_last_run(latest_ts)
    print(f"📝 last_run updated: {latest_ts}")

if __name__ == "__main__":
    main()
