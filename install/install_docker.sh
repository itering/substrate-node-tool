#!/bin/bash

[[ $UID -ne 0 ]] && echo "Require root permission" && exit 1

docker_install_success=1

err_exit() {
    echo $2
    exit $1
}

install_centos() {
    yum remove docker \
                  docker-client \
                  docker-client-latest \
                  docker-common \
                  docker-latest \
                  docker-latest-logrotate \
                  docker-logrotate \
                  docker-engine -y
    yum install -y yum-utils device-mapper-persistent-data lvm2 epel-release jq && \
    yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo && \
    yum install containerd.io docker-ce docker-ce-cli -y && docker_install_success=0 
}

install_ubuntu() {
    apt-get -y remove docker docker-engine docker.io containerd.io
    apt-get update && \
    apt-get -y install jq \
        python3-pip python3-dev \
        libffi-dev libssl-dev gcc libc-dev \
        apt-transport-https \
        ca-certificates \
        curl \
        software-properties-common && \
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add - && \
    # sudo apt-key fingerprint 0EBFCD88
    # pub   4096R/0EBFCD88 2017-02-22
    #      Key fingerprint = 9DC8 5822 9FC7 DD38 854A  E2D8 8D81 803C 0EBF CD88
    # uid                  Docker Release (CE deb) <docker@docker.com>
    # sub   4096R/F273FCD8 2017-02-22
    add-apt-repository \
       "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
       $(lsb_release -cs) \
       stable" && \
    apt-get update && \
    apt-get -y install docker-ce && docker_install_success=0
}

install_compose() {
    if [[ ${docker_install_success} -eq 0 ]]
    then
        docker_compose_releases=$(curl -s https://api.github.com/repos/docker/compose/releases)
        latest_stable_compose=$(echo ${docker_compose_releases} | jq '[.[] | select(.prerelease==false)]' | jq .[0])
        linux_release=$(echo $latest_stable_compose | jq -r '.assets[] | select(.name=="docker-compose-Linux-x86_64") | .browser_download_url')
        linux_release_sha256=$(echo $latest_stable_compose | jq -r '.assets[] | select(.name=="docker-compose-Linux-x86_64.sha256") | .browser_download_url')
        curl -L "${linux_release}" -o /tmp/docker-compose-Linux-x86_64 && \
        curl -L "${linux_release_sha256}" -o /tmp/docker-compose-Linux-x86_64.sha256
        if [[ $? -ne 0 ]]
        then
            err_exit $? "Download docker compose failed"
        fi
        cd /tmp && sha256sum --status -c docker-compose-Linux-x86_64.sha256
        if [[ $? -ne 0 ]]
        then
            err_exit $? "sha256sum docker-compose-Linux-x86_64 failed"
        fi
        [[ -f '/usr/local/bin/docker-compose' ]] && rm -r /usr/local/bin/docker-compose
        [[ -L '/usr/bin/docker-compose' ]] && rm -r /usr/bin/docker-compose
        mv /tmp/docker-compose-Linux-x86_64 /usr/local/bin/docker-compose && \
        chmod +x  /usr/local/bin/docker-compose && \
        ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose && \
        docker version && \
        echo "Docker Compose Version:" && docker-compose --version
        echo "Run 'usermod -a -G docker $(whoami)'"
        usermod -a -G docker $(whoami)
    else
        echo "Docker CE install failed"
    fi
}

install_docker() {
    kernel_release=$(uname -r | cut -d '.' -f 1)
    kernel_release_2=$(uname -r | cut -d '.' -f 2)
    [[ "x${kernel_release}" == "x" ]] && err_exit 1 "Can not get kernel info"
    [[ "x${kernel_release_2}" == "x" ]] && err_exit 1 "Can not get kernel info"
    [[ ${kernel_release} -lt 3 ]] && err_exit 1 "Kernel need >= 3.10"
    if [[ ${kernel_release} -eq 3 ]]
    then
        [[ ${kernel_release_2} -lt 10 ]] && err_exit 1 "Kernel need >= 3.10"
    fi
    if [[ -f '/etc/redhat-release' ]]
    then
        install_centos
    elif [[ -f '/etc/lsb-release' ]] 
    then
        install_ubuntu
    else
        err_exit 1 "Your OS not support"
    fi
}

install_docker
install_compose

exit 0
