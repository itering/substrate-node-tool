#!/usr/bin/env bash


# Install Docker
. install/install_docker.sh
if [[ $? -ne 0 ]]
then
    echo "Install docker failed, exit..."
    exit 1
fi

# Get Images
docker pull darwinianetwork/monitor:0.1 && \
docker pull consul:1.7.1 && \
docker pull iteringops/substrate-ops-python37-glue:0.1