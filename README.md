# Jessica Call Exporter

Автоматическая выгрузка звонков агента Jessica-10 minit в Google Doc.

## 🔧 Setup

1. Добавь Secrets в GitHub:
   - `API_KEY` — ключ ElevenLabs
   - `DOC_ID` — ID Google документа
   - `CREDENTIALS_JSON` — credentials.json от Google Service Account (base64)

2. Убедись, что сервисный аккаунт имеет доступ к Google Doc (`Редактор`).

## 🚀 Автозапуск

Скрипт автоматически запускается каждые 5 минут через GitHub Actions.
