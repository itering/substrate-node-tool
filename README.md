# Substrate Node Tools

## Feature

- One-click deployment of docker containers
- Node start automatically get all bootnodes
- Automatic restart when encountering node synchronization problem
- Automatically detect the latest node docker images
- Can access WebHook for alert
- Support to start multiple nodes at the same time

## Configure

### Configure python virtual environment

```bash
python3 -m pip install --user virtualenv
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

### Modify configuration file

```bash
cp config.json.example config.json
```

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

- pid: The pid file stored by the main process
- session_key: key for session lock, core configuration


> substrate

- id: the id of the current node, unique
- image: docker image
- base_path: data storage path
- node_key (optional): unique identifier after node startup (ed25519)
- validator: whether to run the validator node
- auto_use_latest: whether to use the latest tag image
- prometheus_metrics: monitor metrics, use this to determine the current node synchronization status
- port (optional): p2p network operation port (only)
- ws_port: websocket port (only)
- prometheus_port: prometheus port (only)

## Start the process

    $ python client.py start


## Close process

    $ python client.py stop
    

## System output log

- stdout: /tmp/glue_stdout.log
- stderr: /tmp/glue_stderr.log


## docker 

### install docker 

https://docs.docker.com/compose/install/
    
Linux systems (CentOS and Ubuntu) can be installed with one-click script
    
    ```
    curl -sSL https://gitee.com/x2x4/mytools/raw/master/install_docker.sh | sudo bash
    ```
    
### start
    docker network create substrate-ops
    
    docker-compose up -d   
    
### stop

    docker-compose down


## Suggested solution

1. If you encounter unreachable nodes, it is not a good solution to restart or deploy multiple servers in the same area because of network problems. To avoid this situation, it is recommended to set as many boot_nodes as possible and Deploy in networks in different regions
2. Nodes deployed by centOs have significantly lower memory usage and CPU usage than those on ubuntu
3. If you do not see your own node in telemetry or the current block height is abnormal, it may not necessarily mean that the node did not start successfully or the synchronization is abnormal, it may be a telemetry display problem