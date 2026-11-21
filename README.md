# RemontAI: запуск
1. Ключ: aistudio.google.com -> Get API key. Никому не показывайте и не кладите в GitHub.
2. Залейте папку на GitHub (репозиторий можно сделать приватным).
3. share.streamlit.io -> New app -> выберите репозиторий, файл app.py.
4. Advanced settings -> Secrets: GEMINI_API_KEY = "ваш_ключ"
5. Ссылка на приложение и есть прототип. Откройте её с телефона для проверки.
Локально: pip install -r requirements.txt; streamlit run app.py (ключ в переменной GEMINI_API_KEY).
Если модель не найдена, задайте переменную GEMINI_MODEL названием из AI Studio.

## Каталог
catalog.csv содержит 20 демо-позиций с ОРИЕНТИРОВОЧНЫМИ ценами. Перед защитой замените на реальные:
магазин, ссылка, цена, и поставьте verified=да. Нужно 50-80 позиций; новые работы добавляются строками
с теми же work (walls_paint, walls_wallpaper, floor_laminate, ceiling_paint, plinth).
coverage: сколько м2 (или м) покрывает одна единица за один слой; layers: число слоёв.
