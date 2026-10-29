FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# La API solo lee: se ejecuta sin privilegios.
RUN useradd --system --no-create-home api
USER api
EXPOSE 5050
CMD ["python", "run.py"]
