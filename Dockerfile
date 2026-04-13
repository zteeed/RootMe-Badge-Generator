# Python 3.14 (slim Debian bookworm) — régénérer requirements.txt avec la même version : voir commentaire dans requirements.in
FROM python:3.14-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt
COPY ./ /app

VOLUME /app/storage_clients

ENV API_URL=https://api.www.root-me.org
ENV URL=https://root-me-badge.cloud.duboc.xyz
ENV STORAGE_FOLDER=storage_clients
ENV ROOTME_ACCOUNT_USERNAME=ROOTME_USERNAME
ENV ROOTME_ACCOUNT_PASSWORD=ROOTME_PASSWORD
ENV ROOTME_API_KEY=
ENV LOG_LEVEL=INFO

WORKDIR /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
