#!/usr/bin/env python
# encoding: utf-8

import os
import sys
import docker
import multiprocessing
import time
from libs import daemon
import signal
from docker import errors as docker_errors
from requests.exceptions import ReadTimeout
import requests


class Monitor(multiprocessing.Process):
    _app_cfg = None
    _app_docker_client = None
    _app_docker_instance = {}
    last_block_num = 0
    prometheus_host = "127.0.0.1"

    def __init__(self, cfg: dict, debug=False, *args, **kwargs):
        self.cfg = cfg
        self._debug = debug
        print("Start Success")
        daemon.output_to_log(stdout='/tmp/glue_stdout.log', stderr='/tmp/glue_stderr.log')
        super().__init__(*args, **kwargs)

    @property
    def debug(self):
        return self._debug

    @property
    def cfg(self):
        return self._app_cfg

    @cfg.setter
    def cfg(self, val):
        self._app_cfg = val

    def _send_message(self):
        # todo send alert
        pass

    def _d(self, msg):
        if self._debug:
            print('[PID: %d] [%.3f] %s' % (os.getpid(), time.time(), msg))
            sys.stdout.flush()

    def _app_check(self):
        if self._app_cfg is None:
            raise RuntimeError('cfg not defined')

    def _app_node_init(self):
        if os.getenv("DOCKER_MODE") == "True":
            self._app_docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        else:
            self._app_docker_client = docker.from_env()
        self._debug = self._app_cfg['global']['debug']
        self._app_session_name = "glue_%s" % self._app_cfg['substrate'][0]['id']
        self._app_session_key = self._app_cfg['global']['session_key']

    def _app_docker_pull_image(self, image):
        dc = self._app_docker_client
        try:
            dc.images.get(image)
        except docker_errors.ImageNotFound:
            self._d('Download %s' % image)
            dc.images.pull(image)

    def _app_stop_container(self, node, timeout=30, force=False):
        d = self._d
        name = node['id']
        if name not in self._app_docker_instance:
            return

        if self._app_is_container_running(node):
            d('container alive')
            if force:
                d('force kill')
                self._app_docker_instance[name].kill()
            else:
                self._app_docker_instance[name].stop()
                if not self._app_waiting_container_offline(node, timeout=timeout):
                    d('timeout, force kill')
                    self._app_stop_container(node, force=True)

        self._app_waiting_container_offline(node)
        d('remove container')
        self._app_docker_instance[name].remove()
        del self._app_docker_instance[name]

    def _app_waiting_container_offline(self, node, retry=3, timeout=30):
        _try = 0
        if node['id'] in self._app_docker_instance:
            while _try < retry:
                try:
                    self._d('waiting %d time close' % (_try + 1))
                    rt = self._app_docker_instance[node['id']].wait(
                        timeout=timeout
                    )
                    self._d('stop return: %s' % rt)
                    return True
                except ReadTimeout:
                    _try += 1
        return False

    def _app_add_network(self):
        dc = self._app_docker_client
        try:
            dc.networks.get("substrate-ops")
        except docker_errors.NotFound:
            dc.networks.create("substrate-ops")

    def _app_start_container(self, node):
        image = node['image']
        self._app_docker_pull_image(image)
        self._app_add_network()

        name = node['id']
        name_str = '--name %s' % name

        base_path = dict()
        _path = node['base_path']
        base_path[_path] = {'bind': _path, 'mode': 'rw'}
        base_path_str = "--base-path %s" % _path

        # port map
        ports = dict()
        ports['9944/tcp'] = node['ws_port']
        ports['9615/tcp'] = node['prometheus_port']

        boot_nodes = ""
        if ('boot_nodes' in node) and len(node['boot_nodes']) > 0:
            boot_nodes = "--bootnodes %s" % " ".join(node['boot_nodes'])

        identity_key = ""
        if 'node_key' in node:
            identity_key = "--node-key %s" % node['node_key']

        command = "{base_path} {name} --rpc-cors=all {boot_nodes} {identity_key} --prometheus-external {ws_port} {prometheus_port}".format(
            base_path=base_path_str,
            name=name_str,
            boot_nodes=boot_nodes,
            identity_key=identity_key,
            ws_port="--ws-port %d" % ports['9944/tcp'],
            prometheus_port="--prometheus-port %d" % ports['9615/tcp'],
        )

        if node['validator']:
            command = command + " --validator"
        else:
            # --rpc-external and --ws-external options shouldn\'t be used if the node is running as a validator.
            # Use `--unsafe-rpc-external` if you understand the risks.
            command = command + " --rpc-external --ws-external"

        self._app_docker_instance[name] = self._app_docker_client.containers.run(
            image=image,
            name=name,
            ports=ports,
            volumes=base_path,
            command=command,
            detach=True,
            network='substrate-ops'
        )

    def _app_is_container_running(self, node):
        c_name = node['id']

        if (c_name in self._app_docker_instance) is False:
            try:
                self._app_docker_instance[c_name] = self._app_docker_client.containers.get(c_name)
                return self._app_docker_instance[c_name].status == 'running'
            except docker_errors.NotFound:
                return False
        else:
            self._app_docker_instance[c_name].reload()
            return self._app_docker_instance[c_name].status == 'running'

    def _app_is_validator_working(self, node):

        prometheus_host = '127.0.0.1'
        if os.getenv("DOCKER_MODE") == "True":
            prometheus_host = node['id']

        try:
            url = "http://{prometheus}:{prometheus_port}/metrics".format(prometheus=prometheus_host,
                                                                         prometheus_port=node["prometheus_port"])
            metrics = requests.get(url).text.split("\n")
            current = 0
            for index, v in enumerate(metrics):
                metric = v.split(" ")
                if metric[0] == node['prometheus_metrics']:
                    current = metric[1]
                    break
            print(self.last_block_num, current)
            status = int(current) > self.last_block_num

            self.last_block_num = int(current)
            return status
        except requests.exceptions.ConnectionError:
            print(requests.exceptions.ConnectionError)
            return False
        except Exception as e:
            print(e)
            return False

    def terminate(self, *args, **kwargs):
        print('%s receive process exit signal' % os.getpid())
        sys.stdout.flush()
        for node in self._app_cfg["substrate"]:
            self._app_stop_container(node)

        raise SystemExit(0)

    def run(self):
        signal.signal(signal.SIGTERM, self.terminate)

        self._d('client start')
        self._app_check()
        self._app_node_init()

        try:
            while True:
                self._d('get node status')
                for node in self._app_cfg["substrate"]:
                    if self._app_is_container_running(node):
                        if not self._app_is_validator_working(node):
                            self._d('node sync unusual')
                            self._app_stop_container(node)
                        else:
                            self._d('node sync well!!!!')
                    else:
                        self._d('container start')
                        self._app_start_container(node)
                        self._d('container start success')
                time.sleep(50)
        except Exception as e:
            print(e)
            time.sleep(10)
            raise e
