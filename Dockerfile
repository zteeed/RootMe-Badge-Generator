FROM tiangolo/uwsgi-nginx-flask:python3.7

COPY ./ /app
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ENV API_URL https://api.www.root-me.org
ENV URL https://root-me-badge.hackademint.org
ENV STORAGE_FOLDER storage_clients
ENV ROOTME_ACCOUNT_USERNAME rootme_username
ENV ROOTME_ACCOUNT_PASSWORD password 
