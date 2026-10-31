FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    fastapi langchain-gigachat openpyxl pandas python-dotenv redis python-multipart "uvicorn[standard]"

COPY . .
RUN pip install --no-cache-dir --no-deps -e .

CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]