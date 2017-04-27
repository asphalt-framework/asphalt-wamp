FROM python:3.5.2

RUN adduser -u 1000 testuser
RUN wget -qO- https://github.com/jwilder/dockerize/releases/download/v0.3.0/dockerize-linux-amd64-v0.3.0.tar.gz |\
    tar xzC /usr/local/bin
RUN pip install --no-cache-dir tox
ENTRYPOINT ["dockerize", "-wait", "http://crossbar:8080/", "tox", "-e", "py35"]
