#!/usr/bin/env python
# encoding: utf-8

import json
import os
from jsonschema import validate
from config import boot_nodes

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
                "log_dir": {"type": "string"},
            },
            "required": ["pid", "monitor_interval", "session_key"]
        },
        "consul": {
            "type": "object",
            "properties": {
                "port": {"type": "number"},
                "client": {"type": "string", "minLength": 1},
                "node_key": {"type": "string"},
            },
            "required": ["port", "client"]
        },
        "substrate": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "image": {"type": "string", "minLength": 1},
                "network": {"type": "string", "minLength": 1},
                "port": {"type": "number"},
                "base_path": {"type": "string"},
                "telemetry_url": {"type": "array"},
                "monitor_host": {"type": "string", "minLength": 1},
                "boot_nodes": {"type": "array", "minItems": 1},
            },
            "required": ["image", "monitor_host", "id", "port", "network"]
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
    if "CONSUL_ADDRESS" in os.environ:
        conf["consul"]["client"] = os.getenv("CONSUL_ADDRESS")
    if "CLIENT_NODE_NAME" in os.environ:
        conf["substrate"]["id"] = os.getenv("CLIENT_NODE_NAME")
    if "MONITOR_HOST" in os.environ:
        conf["substrate"]["monitor_host"] = os.getenv("MONITOR_HOST")
    if "CLIENT_NODE_PORT" in os.environ:
        conf["substrate"]["port"] = int(os.getenv("CLIENT_NODE_PORT"))
    if "CLIENT_NODE_KEY" in os.environ:
        conf["substrate"]["node_key"] = os.getenv("CLIENT_NODE_KEY")
    conf["substrate"]["node_key"] = trim_hex(conf["substrate"]["node_key"])
    conf["substrate"]["key_path"] = os.getcwd() + '/sub_key'
    return conf


def trim_hex(s):
    if s.startswith('0x'):
        s = s[2:]
    return s


def auto_insert_boot_nodes(conf):
    print("Start discover boot_nodes")
    boot = boot_nodes.Boot()
    try:
        nodes = boot.run(conf["substrate"]["network"])
        conf["substrate"]["boot_nodes"].extend(nodes)
    except:
        print("from telemetry get boot_nodes error")
    conf["substrate"]["boot_nodes"] = unique_boot_node(conf["substrate"]["boot_nodes"])
    return conf


def unique_boot_node(nodes):
    unique_ip = []
    unique = []
    for i in nodes:
        if i.split('/')[2] not in unique_ip:
            unique_ip.append(i.split('/')[2])
            unique.append(i)

    return unique
