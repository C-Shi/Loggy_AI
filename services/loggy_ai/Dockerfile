FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    git \
    vim

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install -no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app
COPY ./web /code/web

CMD ["sh", "-c", "uvicorn web.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
