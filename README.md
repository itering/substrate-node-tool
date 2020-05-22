# substrate Ops Tools

！当前代码基于python3编写，不支持python2

## Features

- docker 容器一键部署
- 节点启动自动获取所有bootnodes
- 遇到节点同步问题自动重启
- 可接入钉钉talk 机器人进行alert 报警


## 配置

配置虚拟环境

```bash
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

修改配置文件

```bash
cp config.json.example config.json
```

配置内容

```json
{
  "global": {
    "pid": "/tmp/glue.pid",
    "monitor_interval": 1,
    "session_key": "glue",
    "debug": true
  },
  "substrate": {
    "id": "holy",
    "network": "darwinia",
    "image": "darwinianetwork/darwinia:release-v0.5.7",
    "node_key": "0x46e06a6d52fe3508babe698fca9e403bebb09059d2e0bd64d174bc6c114b3557",
    "port": 20222,
    "base_path": "opts/darwinia-ops/data",
    "boot_nodes": [],
    "validator": "true"
  }
}
```

> global:

- pid: 主进程存放的pid文件
- session_key: session锁的key，核心配置


> darwinia

- id: 当前节点的id，唯一
- image: docker镜像
- port: p2p网络运行端口
- base_path: 数据保存路径
- telemetry_url: telemetry url 数组
- boot_nodes(可选): boot_nodes 数组
- node_key(可选): 节点启动后唯一标示符(ed25519)

## 启动进程
    python glue.py start


## 关闭进程
    python glue.py stop
    

## 系统输出的日志

- stdout: /tmp/glue_stdout.log
- stderr: /tmp/glue_stderr.log


## docker 

### install docker 

    https://docs.docker.com/compose/install/
    
    Linux系统(CentOS与Ubuntu)可以用脚本一键安装
    
    ```
    curl -sSL https://gitee.com/x2x4/mytools/raw/master/install_docker.sh | sudo bash
    ```
    
### start
    docker network create substrate-ops
    
    docker-compose up -d   
    
### stop

    docker-compose down


## 建议的方案

1. 如果遇到连不上节点，很大程度因为网络问题，重启或者在同一台区域的服务器进行部署多台都不会是好方案, 为避免这个情况，建议设置尽可能多的 boot_nodes 以及在不同区域的网络中部署
2. centOs部署的节点，内存占用和cpu占用明显比在ubuntu的低很多
3. 若在telemetry没有看到自己的节点或者当前块高不正常，不一定就是节点未启动成功或者是同步不正常，有可能是telemetry显示问题