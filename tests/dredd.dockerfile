FROM python:3.6

WORKDIR /opt
RUN curl -Sl https://deb.nodesource.com/setup_8.x | bash
RUN apt-get install -y nodejs
RUN npm install dredd

CMD ["bash"]
