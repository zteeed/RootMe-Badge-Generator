FROM python:3.7
#  FROM tiangolo/uwsgi-nginx-flask:python3.7

COPY ./requirements.txt /app/requirements.txt
RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt
COPY ./ /app
COPY ./nginx.conf /etc/nginx/nginx.conf

VOLUME /app/storage_clients

ENV API_URL https://api.www.root-me.org
ENV URL https://root-me-badge.cloud.duboc.xyz
ENV STORAGE_FOLDER storage_clients
ENV ROOTME_ACCOUNT_USERNAME ROOTME_USERNAME
ENV ROOTME_ACCOUNT_PASSWORD ROOTME_PASSWORD 

WORKDIR /app
CMD python3 main.py
