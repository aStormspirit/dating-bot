# Собирается из корня репозитория: схеме базы нужен каталог supabase/init.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY chat_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY chat_api/app ./app
COPY supabase ./supabase

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
