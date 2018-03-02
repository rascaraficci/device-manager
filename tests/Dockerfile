FROM device-manager

RUN curl -Sl https://deb.nodesource.com/setup_8.x | bash
RUN apt-get install -y nodejs
RUN npm install dredd

RUN mkdir -p /usr/src/app/tests
ADD . /usr/src/app/tests
RUN pip install -r /usr/src/app/tests/requirements.txt

ENV PYTHONPATH=${PYTHONPATH}:/usr/src/app/DeviceManager

CMD ["./tests/start-test.sh"]