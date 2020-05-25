#!/usr/bin/env python
# encoding: utf-8

import json
import os
from jsonschema import validate
from config import boot_nodes
import requests

schema = {
    "type": "object",
    "properties": {
        "global": {
            "type": "object",
            "properties": {
                "pid": {"type": "string", "minLength": 1},
                "monitor_interval": {"type": "number"},
                "session_key": {"type": "string", "minLength": 1},
                "debug": {"type": "boolean"},
            },
            "required": ["pid", "monitor_interval", "session_key"]
        },
        "substrate": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "image": {"type": "string", "minLength": 1},
                "network": {"type": "string", "minLength": 1},
                "port": {"type": "number"},
                "base_path": {"type": "string"},
                "validator": {"type": "boolean"}
            },
            "required": ["image", "id", "port", "network", "base_path", "validator"]
        },
    },
}


def read_cfg(_cfg):
    if not os.path.exists(_cfg):
        raise OSError('%s not find' % _cfg)
    conf = check_and_read_config(_cfg)
    return merge_env_with_conf(conf)


def check_and_read_config(_cfg):
    with open(_cfg, 'r') as fb:
        try:
            conf = json.load(fb)
        except (json.JSONDecodeError, TypeError, ValueError):
            raise OSError('Read %s json file error' % _cfg)
        validate(instance=conf, schema=schema)
        if type(conf) != dict:
            raise RuntimeError("cfg not dict")
        return conf


def merge_env_with_conf(conf):
    if "CLIENT_NODE_NAME" in os.environ:
        conf["substrate"]["id"] = os.getenv("CLIENT_NODE_NAME")
    if "CLIENT_NODE_PORT" in os.environ:
        conf["substrate"]["port"] = int(os.getenv("CLIENT_NODE_PORT"))
    if "CLIENT_NODE_KEY" in os.environ:
        conf["substrate"]["node_key"] = os.getenv("CLIENT_NODE_KEY")
    if "CLIENT_VALIDATOR" in os.environ:
        conf["substrate"]["validator"] = os.getenv("CLIENT_VALIDATOR") == "true"
    conf["substrate"]["node_key"] = trim_hex(conf["substrate"]["node_key"])
    return conf


def trim_hex(s):
    if s.startswith('0x'):
        s = s[2:]
    return s


def auto_insert_boot_nodes(_cfg):
    print("Start discover boot_nodes")
    boot = boot_nodes.Boot()
    try:
        nodes = boot.run(_cfg["substrate"]["network"])
        _cfg["substrate"]["boot_nodes"].extend(nodes)
    except:
        print("from telemetry get boot_nodes error")
    _cfg["substrate"]["boot_nodes"] = unique_boot_node(_cfg["substrate"]["boot_nodes"])
    return _cfg


def unique_boot_node(nodes):
    unique_ip = []
    unique = []
    for i in nodes:
        if i.split('/')[2] not in unique_ip:
            unique_ip.append(i.split('/')[2])
            unique.append(i)

    return unique


def check_image_latest_version(_cfg):
    if "auto_use_latest" not in _cfg["substrate"] or _cfg["substrate"]["auto_use_latest"] == "false":
        return _cfg
    image = _cfg["substrate"]["image"].split(':')[0]
    hub_url = "https://registry.hub.docker.com/v2/repositories/{image}/tags".format(image=image)
    tags = requests.get(hub_url).json()
    try:
        tag = tags["results"][0]['name']
        _cfg["substrate"]["image"] = image + ":" + tag
        print("use latest image tag", _cfg["substrate"]["image"])
    except Exception as e:
        print(e)
    return _cfg
