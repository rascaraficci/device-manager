FROM python:3.6-alpine

WORKDIR /usr/src/app
ENV PYTHONPATH=":/usr/src/app"
EXPOSE 5000
CMD ["./docker/entrypoint.sh"]

RUN mkdir -p /usr/src/app/requirements && \
    apk --no-cache add postgresql-dev gcc musl-dev
ADD requirements/requirements.txt requirements/
RUN pip install -r requirements/requirements.txt && apk del gcc

ADD . /usr/src/app
