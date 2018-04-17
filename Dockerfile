FROM python:3.6

RUN mkdir -p /usr/src/app/requirements
WORKDIR /usr/src/app

ADD requirements/requirements.txt requirements/
RUN pip install -r requirements/requirements.txt

ADD . /usr/src/app

ENV PYTHONPATH=":/usr/src/app"
EXPOSE 5000
CMD ["./docker/entrypoint.sh"]
