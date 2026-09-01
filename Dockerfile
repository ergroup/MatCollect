FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ ./src/
COPY pages/ ./pages/
COPY assets/ ./assets/
COPY .streamlit/ ./.streamlit/
COPY app.py .

RUN pip install --no-cache-dir .

ENV APP_DIR=/app

EXPOSE 8501

CMD ["matcollect"]
