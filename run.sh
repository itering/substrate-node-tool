#!/usr/bin/env bash


function build(){
    docker-compose build
}

function run(){
    docker-compose up -d
}

function stop(){
     docker-compose down
}

if [[ "$1" == "" ]]; then
    build
elif [[ "$1" == "run" ]]; then
    run
elif [[ "$1" == "stop" ]]; then
    stop
else
    build
fi