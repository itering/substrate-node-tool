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
                "session_key": {"type": "string", "minLength": 1},
                "debug": {"type": "boolean"},
            },
            "required": ["pid", "session_key"]
        },
        "substrate": {
            "type": "array",
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "image": {"type": "string", "minLength": 1},
                "network": {"type": "string", "minLength": 1},
                "port": {"type": "number"},
                "base_path": {"type": "string"},
                "prometheus_metrics": {"type": "string"},
                "validator": {"type": "boolean"},
                "ws_port": {"type": "number"},
                "prometheus_port": {"type": "number"},
            },
            "required": ["image", "id", "network", "base_path", "validator", "prometheus_metrics", "ws_port",
                         "prometheus_port"]
        },
    },
}


def read_cfg(_cfg):
    if not os.path.exists(_cfg):
        raise OSError('%s not find' % _cfg)
    conf = check_and_read_config(_cfg)
    return conf


def check_and_read_config(_cfg):
    with open(_cfg, 'r') as fb:
        try:
            conf = json.load(fb)
        except (json.JSONDecodeError, TypeError, ValueError):
            raise OSError('Read %s json file error' % _cfg)
        validate(instance=conf, schema=schema)
        if type(conf) != dict:
            raise RuntimeError("cfg not dict")
        check_unique_column(conf, ["id", "ws_port", "prometheus_port"])
        return conf


def trim_hex(s):
    if s.startswith('0x'):
        s = s[2:]
    return s


def auto_insert_boot_nodes(_cfg):
    print("Start discover boot_nodes")
    boot = boot_nodes.Boot()
    for i in range(len(_cfg["substrate"])):
        nodes = boot.run(_cfg["substrate"][i]["network"])
        _cfg["substrate"][i]["boot_nodes"] = unique_boot_node(nodes)
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


def check_unique_column(_cfg, columns):
    def check(column):
        unique = []
        for node in _cfg["substrate"]:
            if node[column] not in unique:
                unique.append(node[column])
            else:
                raise KeyError("duplicate key {column}".format(column=column))

    list(map(lambda x: check(x), columns))
