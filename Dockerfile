FROM python:3.9.18-slim-bullseye

WORKDIR /app

COPY ./ /app/

RUN pip install --no-cache-dir -r requirements.txt

ENV TELEGRAM_BOT_API_KEY=""
ENV GEMINI_API_KEYS=""
ENV SUPABASE_URL=""
ENV SUPABASE_API_KEY=""

CMD ["sh", "-c", "python main.py ${TELEGRAM_BOT_API_KEY} ${GEMINI_API_KEYS} ${SUPABASE_URL} ${SUPABASE_API_KEY}"]
