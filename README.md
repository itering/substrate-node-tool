# substrate Ops Tools

## 特性

- docker 容器一键部署
- 节点启动自动获取所有bootnodes
- 遇到节点同步问题自动重启
- 可自动检测最新的节点docker images
- 可接入WebHook 进行 alert 报警
- 支持同时启动多节点

## 配置

配置python 虚拟环境

```bash
python3 -m pip install --user virtualenv
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
  "substrate": [
    {
      "id": "darwinia-ops1",
      "network": "darwinia",
      "image": "darwinianetwork/darwinia:release-v0.6.0",
      "base_path": "opts/darwinia-ops/data",
      "auto_use_latest": "true",
      "validator": false,
      "prometheus_metrics": "darwinia_block_height{status=\"best\"}",
      "port": 20222,
      "ws_port": 9944,
      "prometheus_port": 9615
    },
    {
      "id": "kusama-ops1",
      "network": "kusama",
      "image": "polkasource/substrate-client:kusama-latest",
      "base_path": "opts/darwinia-ops/data",
      "auto_use_latest": "true",
      "validator": false,
      "prometheus_metrics": "polkadot_block_height{status=\"best\"}",
      "port": 20223,
      "ws_port": 9944,
      "prometheus_port": 9619
    }
  ]
}
```

> global:

- pid: 主进程存放的pid文件
- session_key: session锁的key，核心配置


> substrate

- id: 当前节点的id，唯一
- image: docker镜像
- base_path: 数据保存路径
- node_key(可选): 节点启动后唯一标示符(ed25519)
- validator: 是否跑验证人节点
- auto_use_latest: 是否使用最新tag的image  
- prometheus_metrics: 监听指标，通过该指标判断当前节点同步状况
- port(可选): p2p网络运行端口(唯一)
- ws_port： websocket 端口(唯一)
- prometheus_port： prometheus 端口(唯一)

## 启动进程

    $ python client.py start


## 关闭进程

    $ python client.py stop
    

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