#!/usr/bin/env python3

import os
import time
import datetime
import requests
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

API_KEY = os.environ.get("API_KEY")
DOC_ID = os.environ.get("DOC_ID")
AGENT_NAME_FILTER = "Jessica-10 minit"
PAGE_SIZE = 100
MIN_DURATION = 60
TZ_OFFSET_HOURS = 4
LAST_RUN_FILE = "last_run.txt"
SCOPES = ["https://www.googleapis.com/auth/documents"]

def get_docs_service():
    credentials = service_account.Credentials.from_service_account_file(
        "credentials.json", scopes=SCOPES
    )
    return build("docs", "v1", credentials=credentials)

def fetch_all_calls():
    session = requests.Session()
    session.headers.update({
        "xi-api-key": API_KEY,
        "Accept": "application/json"
    })
    url = "https://api.elevenlabs.io/v1/convai/conversations"
    params = {"page_size": PAGE_SIZE}
    all_calls = []
    while True:
        r = session.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        for call in data.get("conversations", []):
            if call.get("agent_name") == AGENT_NAME_FILTER:
                all_calls.append(call)
        if not data.get("has_more"):
            break
        params["cursor"] = data.get("next_cursor")
    return all_calls

def fetch_call_detail(conversation_id):
    url = f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}"
    r = requests.get(url, headers={"xi-api-key": API_KEY})
    r.raise_for_status()
    return r.json()

def load_last_run():
    return int(open(LAST_RUN_FILE).read().strip()) if os.path.exists(LAST_RUN_FILE) else 0

def save_last_run(timestamp):
    with open(LAST_RUN_FILE, "w") as f:
        f.write(str(int(timestamp)))

def format_call(detail, fallback_ts):
    st = detail.get("metadata", {}).get("start_time_unix_secs", fallback_ts)
    adjusted_ts = st + TZ_OFFSET_HOURS * 3600
    ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(adjusted_ts))
    summary = detail.get("analysis", {}).get("transcript_summary", "").strip()
    transcript = detail.get("transcript", [])
    lines = []
    prev_role = None
    for msg in transcript:
        role = msg.get("role", "").upper()
        text = msg.get("message", "").strip()
        if not text:
            continue
        tsec = msg.get("time_in_call_secs", 0.0)
        line = f"[{tsec:06.2f}s] {role}: {text}"
        if prev_role and prev_role != role:
            lines.append("")
        if prev_role == role:
            lines[-1] += "\n" + line
        else:
            lines.append(line)
        prev_role = role
    header = f"=== Call at {ts_str} ===\n"
    if summary:
        header += f"Summary:\n{summary}\n"
    return header + "\n" + "\n".join(lines) + "\n\n" + "―" * 40 + "\n\n"

def main():
    docs_service = get_docs_service()
    calls = fetch_all_calls()
    relevant_calls = [c for c in calls if c.get("call_duration_secs", 0) > MIN_DURATION]
    last_ts = load_last_run()
    new_calls = [c for c in relevant_calls if c.get("start_time_unix_secs", 0) > last_ts]
    if not new_calls:
        print("Нет новых звонков.")
        return

    new_calls.sort(key=lambda x: x["start_time_unix_secs"])
    full_text = ""
    max_ts = last_ts
    for call in new_calls:
        cid = call["conversation_id"]
        fallback = call.get("start_time_unix_secs", 0)
        detail = fetch_call_detail(cid)
        block = format_call(detail, fallback)
        full_text += block
        ts = detail.get("metadata", {}).get("start_time_unix_secs", fallback)
        if ts > max_ts:
            max_ts = ts

    docs_service.documents().batchUpdate(
        documentId=DOC_ID,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": full_text}}]}
    ).execute()
    save_last_run(max_ts)
    print(f"Добавлено {len(new_calls)} звонков.")

if __name__ == "__main__":
    main()
