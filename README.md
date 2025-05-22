# Jessica Call Exporter

Автоматическая выгрузка звонков агента (ID: Ett5Z2WyqmkwilmtCCYJ) в Google Doc.

## 🚀 Установка

1. Создай репозиторий на GitHub
2. Залей содержимое этого архива
3. Добавь Secrets:
   - `API_KEY` — ключ ElevenLabs
   - `DOC_ID` — ID Google-документа
   - `CREDENTIALS_JSON` — base64 от `credentials.json` сервисного аккаунта

## 🔁 Автоматизация

Скрипт запускается каждые 5 минут через GitHub Actions. Только новые звонки добавляются.

