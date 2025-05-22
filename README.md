# Jessica Call Exporter (OAuth версия)

## 🚀 Первый запуск

1. Установи зависимости:

```bash
pip install -r requirements.txt
```

2. Запусти локально:

```bash
python export_calls.py
```

3. Пройди Google OAuth в браузере. Сохранится `token.pickle`.

4. Добавь в GitHub:

- `export_calls.py`
- `requirements.txt`
- `token.pickle`
- `credentials.json` (Desktop client)
- `.github/workflows/export.yml`

5. Добавь в Secrets:
- `API_KEY` — от ElevenLabs
- `DOC_ID` — Google Doc ID

✅ Готово. Actions будет запускаться каждые 5 минут и добавлять новые звонки.

