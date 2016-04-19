#!/bin/sh
docker run --rm -p 8080:8080 -v $PWD/.crossbar/config.yaml:/etc/config.yaml:ro crossbario/crossbar --config /etc/config.yaml
