import os
import json
import time
import pickle
import requests
from google.auth.transport.requests import Request

# === КОНФИГ ===
AGENT_ID = "Ett5Z2WyqmkwilmtCCYJ"
DOC_ID = "1iFo9n49wVAhYfdHQVBzypcm-SzuyY0DCqqpt6Ko4fM4"
API_KEY = "sk_91b455debc341646af393b6582573e06c70458ce8c0e51d4"
TOKEN_PATH = "token.pickle"
LAST_RUN_FILE = "last_run.txt"

# === ACCESS TOKEN ===
def get_access_token():
    with open(TOKEN_PATH, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds.token

# === ВРЕМЯ ПОСЛЕДНЕГО ЗАПУСКА ===
def load_last_ts():
    return int(open(LAST_RUN_FILE).read().strip()) if os.path.exists(LAST_RUN_FILE) else 0

def save_last_ts(ts):
    with open(LAST_RUN_FILE, "w") as f:
        f.write(str(ts))

# === ЗАПРОСЫ К ELEVENLABS ===
def fetch_all_calls():
    all_calls = []
    cursor = None
    headers = {"xi-api-key": API_KEY}
    while True:
        url = "https://api.elevenlabs.io/v1/convai/conversations"
        params = {"page_size": 100}
        if cursor:
            params["cursor"] = cursor
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        calls = [c for c in data.get("conversations", []) if c.get("agent_id") == AGENT_ID]
        all_calls.extend(calls)
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return all_calls

def fetch_call_detail(cid):
    url = f"https://api.elevenlabs.io/v1/convai/conversations/{cid}"
    r = requests.get(url, headers={"xi-api-key": API_KEY})
    r.raise_for_status()
    return r.json()

# === ФОРМАТИРОВКА ===
def format_call(detail, fallback_ts):
    st = detail.get("metadata", {}).get("start_time_unix_secs", fallback_ts)
    ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st))
    transcript = detail.get("transcript", [])
    summary = detail.get("analysis", {}).get("transcript_summary", "").strip()
    lines = [f"=== Call at {ts_str} ==="]
    if summary:
        lines.append(f"Summary:\n{summary}")
    prev = None
    for msg in transcript:
        role = (msg.get("role") or "").upper()
        text = (msg.get("message") or "").strip()
        if not text:
            continue
        tsec = msg.get("time_in_call_secs", 0.0)
        line = f"[{tsec:06.2f}s] {role}: {text}"
        if prev and prev != role:
            lines.append("")
        if prev == role:
            lines[-1] += "\n" + line
        else:
            lines.append(line)
        prev = role
    return "\n".join(lines) + "\n\n" + "―" * 40 + "\n\n"

# === ГЛАВНАЯ ЛОГИКА ===
def main():
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "If-Match": "*"
    }

    print("Загружаем звонки...")
    all_calls = fetch_all_calls()
    print(f"Всего звонков от агента ID={AGENT_ID}: {len(all_calls)}")

    last_ts = load_last_ts()
    new_calls = [
        c for c in all_calls
        if c.get("start_time_unix_secs", 0) > last_ts
    ]
    print(f"Новых звонков: {len(new_calls)}")
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
        max_ts = max(max_ts, fallback)

    # Формируем тело запроса Google Docs API
    requests_body = [{
        "insertText": {
            "location": {"index": 1},
            "text": full_text
        }
    }]

    r = requests.post(
        f"https://docs.googleapis.com/v1/documents/{DOC_ID}:batchUpdate",
        headers=headers,
        data=json.dumps({"requests": requests_body})
    )
    r.raise_for_status()
    save_last_ts(max_ts)
    print(f"✅ Добавлено {len(new_calls)} звонков в Google Doc.")

if __name__ == "__main__":
    main()
