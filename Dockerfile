FROM python:3.6-alpine

RUN mkdir -p /usr/src/app/requirements
WORKDIR /usr/src/app

ADD requirements/requirements.txt requirements/
RUN apk update && \
    apk add postgresql-dev gcc musl-dev && \
    pip install -r requirements/requirements.txt && \
    apk del gcc

ADD . /usr/src/app

ENV PYTHONPATH=":/usr/src/app"
EXPOSE 5000
CMD ["./docker/entrypoint.sh", "start"]
