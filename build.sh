#!/bin/bash

cd "$(dirname "$0")"

podman build --pull=never --platform linux/amd64 -t pyoebase:12.2.13 .
podman push pyoebase:12.2.13 docker.io/incrediblestorm/pyoebase:12.2.13