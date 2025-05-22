#!/usr/bin/env python3

import os
import time
import requests
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ----------------- НАСТРОЙКИ -----------------
API_KEY = "sk_91b455debc341646af393b6582573e06c70458ce8c0e51d4"
DOC_ID = "1iFo9n49wVAhYfdHQVBzypcm-SzuyY0DCqqpt6Ko4fM4"
PAGE_SIZE = 100
LAST_RUN_FILE = "last_run.txt"
CREDENTIALS = "credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]
TZ_OFFSET_HOURS = 4
AGENT_ID_FILTER = "Ett5Z2WyqmkwilmtCCYJ"

# ----------------- Google OAuth -----------------
def get_credentials():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS, SCOPES)
            creds = flow.run_local_server(port=0, access_type="offline", include_granted_scopes=True)
        with open("token.pickle", "wb") as f:
            pickle.dump(creds, f)
    return creds

creds = get_credentials()
docs_service = build("docs", "v1", credentials=creds)

# ----------------- ConvAI API -----------------
session = requests.Session()
session.headers.update({
    "xi-api-key": API_KEY,
    "Accept": "application/json"
})

def fetch_all_calls():
    url = "https://api.elevenlabs.io/v1/convai/conversations"
    params = {"page_size": PAGE_SIZE}
    all_calls = []
    while True:
        r = session.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        calls = data.get("conversations", [])
        for call in calls:
            if call.get("agent_id", "") == AGENT_ID_FILTER:
                all_calls.append(call)
        if not data.get("has_more", False):
            break
        params["cursor"] = data.get("next_cursor")
    return all_calls

def fetch_call_detail(conversation_id):
    r = session.get(f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}")
    r.raise_for_status()
    return r.json()

# ----------------- Вспомогательные функции -----------------
def load_last_run():
    return int(open(LAST_RUN_FILE).read().strip()) if os.path.exists(LAST_RUN_FILE) else 0

def save_last_run(timestamp):
    with open(LAST_RUN_FILE, "w") as f:
        f.write(str(int(timestamp)))

# ----------------- Форматирование звонка -----------------
def format_call(detail, fallback_ts):
    st = detail.get("metadata", {}).get("start_time_unix_secs", fallback_ts)
    adjusted_ts = st + (TZ_OFFSET_HOURS * 3600)
    ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(adjusted_ts))

    analysis = detail.get("analysis") or {}
    summary = (analysis.get("transcript_summary") or "").strip()

    transcript = detail.get("transcript", [])
    lines = []
    prev_role = None
    for msg in transcript:
        role = (msg.get("role") or "").upper()
        text = (msg.get("message") or "").strip()
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

# ----------------- Основной процесс -----------------
def main():
    calls = fetch_all_calls()
    print(f"Всего звонков от агента ID {AGENT_ID_FILTER}: {len(calls)}")

    last_ts = load_last_run()
    new_calls = [c for c in calls if c.get("start_time_unix_secs", 0) > last_ts]
    print(f"Новых звонков: {len(new_calls)}")
    if not new_calls:
        print("Нет новых звонков для добавления.")
        return

    new_calls.sort(key=lambda x: x["start_time_unix_secs"], reverse=True)
    full_text = ""
    max_ts = last_ts
    for call in new_calls:
        cid = call["conversation_id"]
        fallback = call.get("start_time_unix_secs", 0)
        detail = fetch_call_detail(cid)
        block = format_call(detail, fallback)
        full_text += block
        call_ts = detail.get("metadata", {}).get("start_time_unix_secs") or fallback
        if call_ts > max_ts:
            max_ts = call_ts

    if not full_text.strip():
        print("Пустой текст, ничего не добавляем.")
        return

    try:
        print(f"Всего символов в тексте: {len(full_text)}")
        insert_index = 1  # безопасная вставка в начало

        chunk_size = 4000  # можно регулировать
        chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]

        for idx, chunk in enumerate(chunks):
            request = {
                "requests": [{
                    "insertText": {
                        "location": {"index": insert_index},
                        "text": chunk
                    }
                }]
            }
            docs_service.documents().batchUpdate(
                documentId=DOC_ID,
                body=request
            ).execute()
            insert_index += len(chunk)
            print(f"✅ Вставлен чанк {idx + 1}/{len(chunks)} ({len(chunk)} символов)")

        print(f"🎯 Все чанки вставлены. Сохраняем max_ts: {max_ts}")
        save_last_run(max_ts)

    except Exception as e:
        print(f"❌ Ошибка при вставке: {e}")

if __name__ == "__main__":
    main()
