#!/usr/bin/env python3

import os
import time
import requests
import pickle
from datetime import datetime
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ---------------- НАСТРОЙКИ ---------------- #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_KEY = "sk_91b455debc341646af393b6582573e06c70458ce8c0e51d4"
DOC_ID = "1iFo9n49wVAhYfdHQVBzypcm-SzuyY0DCqqpt6Ko4fM4"
PAGE_SIZE = 100
LAST_RUN_FILE = os.path.join(BASE_DIR, "last_run.txt")
CREDENTIALS = os.path.join(BASE_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive.file"]
TZ_OFFSET_HOURS = 4
AGENT_ID_FILTER = "Ett5Z2WyqmkwilmtCCYJ"
CHUNK_SIZE = 100000

# ---------------- AUTH ---------------- #
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

# ---------------- ЗВОНКИ ---------------- #
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
            if call.get("agent_id") == AGENT_ID_FILTER:
                all_calls.append(call)
        if not data.get("has_more"):
            break
        params["cursor"] = data.get("next_cursor")
    return all_calls

def fetch_call_detail(cid):
    try:
        r = session.get(f"https://api.elevenlabs.io/v1/convai/conversations/{cid}", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        print(f"⏱ Таймаут при запросе звонка {cid} — пропускаем")
        return {}
    except Exception as e:
        print(f"❌ Ошибка при получении звонка {cid}: {e}")
        return {}

# ---------------- УТИЛИТЫ ---------------- #
def load_last_run():
    if os.path.exists(LAST_RUN_FILE):
        try:
            with open(LAST_RUN_FILE, "r") as f:
                return int(f.read().strip())
        except:
            print("⚠️ Ошибка чтения last_run.txt")
    return 0

def save_last_run(ts):
    try:
        with open(LAST_RUN_FILE, "w") as f:
            f.write(str(int(ts)))
        print(f"💾 last_run.txt обновлён: {ts}")
    except Exception as e:
        print(f"❌ Ошибка записи last_run.txt: {e}")

def format_call(detail, fallback_ts):
    ts = detail.get("metadata", {}).get("start_time_unix_secs") or fallback_ts
    adjusted = ts + (TZ_OFFSET_HOURS * 3600)
    dt_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(adjusted))

    summary = (detail.get("analysis") or {}).get("transcript_summary", "").strip()
    transcript = detail.get("transcript", [])

    header = f"=== Call at {dt_str} ===\n"
    if summary:
        header += f"Summary:\n{summary}\n"
    lines = []
    prev_role = None
    for msg in transcript:
        role = (msg.get("role") or "").upper()
        text = (msg.get("message") or "").strip()
        if not text:
            continue
        t = msg.get("time_in_call_secs", 0.0)
        line = f"[{t:06.2f}s] {role}: {text}"
        if prev_role and prev_role != role:
            lines.append("")
        if prev_role == role:
            lines[-1] += "\n" + line
        else:
            lines.append(line)
        prev_role = role
    return header + "\n" + "\n".join(lines) + "\n\n" + "―" * 40 + "\n\n"

# ---------------- ОСНОВА ---------------- #
def main():
    print("🚀 Начинаем экспорт звонков")
    calls = fetch_all_calls()
    print(f"📦 Всего звонков от агента {AGENT_ID_FILTER}: {len(calls)}")

    last_ts = load_last_run()
    print(f"⏱ Последний экспорт: {last_ts} ({datetime.utcfromtimestamp(last_ts)})")

    new_calls = []
    for call in calls:
        ts = call.get("start_time_unix_secs", 0)
        print(f"→ Звонок: {ts} | {call.get('conversation_id')}")
        if ts > last_ts:
            new_calls.append(call)

    if not new_calls:
        print("🔕 Нет новых звонков для выгрузки")
        return

    new_calls.sort(key=lambda c: c.get("start_time_unix_secs", 0))
    full_text = ""
    max_ts = last_ts

    for call in new_calls:
        cid = call["conversation_id"]
        fallback_ts = call.get("start_time_unix_secs", 0)
        detail = fetch_call_detail(cid)
        time.sleep(0.5)
        if not detail:
            continue
        block = format_call(detail, fallback_ts)
        full_text += block
        ts = detail.get("metadata", {}).get("start_time_unix_secs") or fallback_ts
        if ts > max_ts:
            max_ts = ts

    if not full_text.strip():
        print("⚠️ Пустой текст — ничего не вставляем")
        return

    try:
        chunks = [full_text[i:i + CHUNK_SIZE] for i in range(0, len(full_text), CHUNK_SIZE)]
        print(f"✂️ Разбили на {len(chunks)} чанков по {CHUNK_SIZE} символов")

        insert_index = 1
        for i, chunk in enumerate(chunks):
            docs_service.documents().batchUpdate(documentId=DOC_ID, body={
                "requests": [{
                    "insertText": {
                        "location": {"index": insert_index},
                        "text": chunk
                    }
                }]
            }).execute()
            insert_index += len(chunk)
            print(f"✅ Вставлен чанк {i + 1}/{len(chunks)}")

        print(f"🏁 Все звонки добавлены. Обновляем last_run: {max_ts}")
        save_last_run(max_ts)

    except Exception as e:
        print(f"❌ Ошибка при вставке в Google Doc: {e}")

if __name__ == "__main__":
    main()
