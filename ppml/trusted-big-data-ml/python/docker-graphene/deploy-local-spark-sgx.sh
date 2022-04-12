#!/bin/bash

export ENCLAVE_KEY_PATH=/home/criteo/BigDL/ppml/trusted-big-data-ml/python/docker-graphene/enclave-key.pem
export DATA_PATH=/home/criteo/BigDL/ppml/trusted-big-data-ml/python/docker-graphene/data
export KEYS_PATH=/home/criteo/BigDL/ppml/trusted-big-data-ml/python/docker-graphene/keys
export LOCAL_IP=127.0.0.1
export DOCKER_IMAGE=intelanalytics/bigdl-ppml-trusted-big-data-ml-python-graphene:0.14.0-SNAPSHOT

sudo docker pull $DOCKER_IMAGE

sudo docker run -itd \
    --privileged \
    --net=host \
    --cpuset-cpus="0-5" \
    --oom-kill-disable \
    --device=/dev/gsgx \
    --device=/dev/sgx/enclave \
    --device=/dev/sgx/provision \
    -v $ENCLAVE_KEY_PATH:/graphene/Pal/src/host/Linux-SGX/signer/enclave-key.pem \
    -v /var/run/aesmd/aesm.socket:/var/run/aesmd/aesm.socket \
    -v $DATA_PATH:/ppml/trusted-big-data-ml/work/data \
    -v $KEYS_PATH:/ppml/trusted-big-data-ml/work/keys \
    --name=spark-local \
    -e LOCAL_IP=$LOCAL_IP \
    -e SGX_MEM_SIZE=16G \
    $DOCKER_IMAGE bash
