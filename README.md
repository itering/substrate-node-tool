# substrate Ops Tools

！当前代码基于python3编写，不支持python2

## 部署consul

[consul.io] https://www.consul.io/docs/install/index.html

可参考 docker-compose.ops.yml

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
    "debug": true,
  },
  "consul": {
    "port": 8500,
    "client": "127.0.0.1"
  },
  "substrate": {
    "id": "finish_holy",
    "network": "darwinia",
    "image": "darwinianetwork/darwinia:release-v0.4.6.2",
    "node_key": "0x46e06a6d52fe3508babe698fca9e403bebb09059d2e0bd64d174bc6c114b3557",
    "port": 20222,
    "base_path": "/tmp/fff",
    "telemetry_url": [
      "ws://telemetry.polkadot.io:1024/"
    ],
    "monitor_host": "192.168.1.163:24855",
    "boot_nodes": [
      "/ip4/152.32.186.6/tcp/30333/p2p/QmdkBsuJPfeuHZDmt9RdcFBcCX99LD9VZ2EdyHrxAmnRCa"
    ]
  }
}
```

> global:

- pid: 主进程存放的pid文件
- monitor_interval: 守护进程监控业务进程的间隔，单位秒
- session_key: session锁的key，核心配置


> consul:

- port: consul client的端口(API端口)
- client: consul client的IP

> darwinia

- id: 当前节点的id，唯一
- image: docker镜像
- port: p2p网络运行端口
- base_path: 数据保存路径
- telemetry_url: telemetry url 数组
- monitor_host: 监控地址 ip:port 格式
- boot_nodes: boot_nodes 数组
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
    
    docker-compose -f docker-compose.ops.yml up -d && docker-compose up -d   
    
### stop

    docker-compose down  && docker-compose -f docker-compose.ops.yml down 


## 存在的问题

1. 非正常关闭ops, consul kv 还是会标记stopping|runner, 重启后会报错，需要手动先删除对应kv缓存


## 开启alert

1. monitor 在遇到长时间不同步块的时候会发出alert,可配置 docker-compose.ops.yml ``DING_TALK_TOKEN``
2. 钉钉机器人文档 https://ding-doc.dingtalk.com/doc#/serverapi2/qf2nxq

## 启动多个节点

1. 修改 docker-compose.yml
2. 添加多个ops service, 注意修改 ``CLIENT_NODE_NAME`` 是节点名。``CONSUL_ADDRESS``，``MONITOR_HOST``都为consul和monitor对应的机器ip

## 建议的方案

1. 如果遇到连不上节点，很大程度因为网络问题，重启或者在同一台区域的服务器进行部署多台都不会是好方案, 为避免这个情况，建议设置尽可能多的 boot_nodes 以及在不同区域的网络中部署
2. centOs部署的节点，内存占用和cpu占用明显比在ubuntu的低很多(?)
3. 若在telemetry没有看到自己的节点或者当前块高不正常，不一定就是节点未启动成功或者是同步不正常，有可能是telemetry显示问题