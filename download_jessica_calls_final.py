#!/usr/bin/env python3

import os
import time
import requests
import pickle
from datetime import datetime
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# === НАСТРОЙКИ === #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_KEY = "sk_91b455debc341646af393b6582573e06c70458ce8c0e51d4"
DOC_ID = "1iFo9n49wVAhYfdHQVBzypcm-SzuyY0DCqqpt6Ko4fM4"
PAGE_SIZE = 100
CHUNK_SIZE = 100000
LAST_RUN_FILE = os.path.join(BASE_DIR, "last_run.txt")
CREDENTIALS = os.path.join(BASE_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive.file"]
AGENT_ID_FILTER = "Ett5Z2WyqmkwilmtCCYJ"
TZ_OFFSET_HOURS = 4

# === AUTH === #
def get_credentials():
    creds = None
    token_path = os.path.join(BASE_DIR, "token.pickle")
    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS, SCOPES)
            creds = flow.run_local_server(port=0, access_type="offline", include_granted_scopes=True)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
    return creds

creds = get_credentials()
docs_service = build("docs", "v1", credentials=creds)

session = requests.Session()
session.headers.update({"xi-api-key": API_KEY, "Accept": "application/json"})

# === ЗВОНКИ === #
def fetch_all_calls():
    url = "https://api.elevenlabs.io/v1/convai/conversations"
    params = {"page_size": PAGE_SIZE}
    all_calls = []
    while True:
        print(f"🌐 Получаем звонки: cursor={params.get('cursor')}")
        r = session.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        for call in data.get("conversations", []):
            if call.get("agent_id") == AGENT_ID_FILTER:
                all_calls.append(call)
        if not data.get("has_more"): break
        params["cursor"] = data.get("next_cursor")
    return all_calls

def fetch_call_detail(cid):
    try:
        r = session.get(f"https://api.elevenlabs.io/v1/convai/conversations/{cid}", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        print(f"⏱ Таймаут при звонке {cid} — пропуск")
    except Exception as e:
        print(f"❌ Ошибка при звонке {cid}: {e}")
    return {}

# === УТИЛИТЫ === #
def load_last_run():
    try:
        with open(LAST_RUN_FILE) as f:
            return int(f.read().strip())
    except:
        return 0

def save_last_run(ts):
    try:
        with open(LAST_RUN_FILE, "w") as f:
            f.write(str(int(ts)))
        print(f"💾 last_run.txt обновлён: {ts}")
    except Exception as e:
        print(f"❌ Ошибка записи last_run: {e}")

def format_call(detail, fallback_ts):
    ts = detail.get("metadata", {}).get("start_time_unix_secs") or fallback_ts
    adjusted = ts + (TZ_OFFSET_HOURS * 3600)
    dt_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(adjusted))
    summary = (detail.get("analysis") or {}).get("transcript_summary", "").strip()
    transcript = detail.get("transcript", [])
    lines = []
    prev_role = None
    for msg in transcript:
        role = (msg.get("role") or "").upper()
        text = (msg.get("message") or "").strip()
        if not text: continue
        t = msg.get("time_in_call_secs", 0.0)
        line = f"[{t:06.2f}s] {role}: {text}"
        if prev_role and prev_role != role: lines.append("")
        if prev_role == role: lines[-1] += "\n" + line
        else: lines.append(line)
        prev_role = role
    header = f"=== Call at {dt_str} ===\n"
    if summary: header += f"Summary:\n{summary}\n"
    return header + "\n" + "\n".join(lines) + "\n\n" + "―" * 40 + "\n\n"

# === MAIN === #
def main():
    print("🚀 Экспорт новых звонков")
    calls = fetch_all_calls()
    last_ts = load_last_run()
    new_calls = [c for c in calls if c.get("start_time_unix_secs", 0) > last_ts]
    if not new_calls:
        print("✅ Новых звонков нет")
        return

    # ⬇️ ВАЖНО: сортируем по убыванию — чтобы свежие были первыми
    new_calls.sort(key=lambda c: c["start_time_unix_secs"], reverse=True)

    full_text = ""
    max_ts = last_ts

    for call in new_calls:
        cid = call["conversation_id"]
        fallback = call.get("start_time_unix_secs", 0)
        detail = fetch_call_detail(cid)
        time.sleep(0.5)
        if not detail: continue
        full_text += format_call(detail, fallback)
        ts = detail.get("metadata", {}).get("start_time_unix_secs") or fallback
        if ts > max_ts:
            max_ts = ts

    if not full_text.strip():
        print("⚠️ Нечего вставлять")
        return

    try:
        chunks = [full_text[i:i + CHUNK_SIZE] for i in range(0, len(full_text), CHUNK_SIZE)]

        for i, chunk in enumerate(reversed(chunks)):
            docs_service.documents().batchUpdate(documentId=DOC_ID, body={
                "requests": [{
                    "insertText": {
                        "location": {"index": 1},
                        "text": chunk
                    }
                }]
            }).execute()
            print(f"✅ Вставлен чанк {i + 1}/{len(chunks)} в начало")

        save_last_run(max_ts)
    except Exception as e:
        print(f"❌ Ошибка вставки в документ: {e}")

if __name__ == "__main__":
    main()
