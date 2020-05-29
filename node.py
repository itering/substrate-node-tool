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
    _app_docker_instance = None
    _app_status = {
        "id": None,
        "status": "stop",
        "heartbeat": 0,
    }
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
        # todo 发送报警
        pass

    def _d(self, msg):
        if self._debug:
            print('[PID: %d] [%.3f] %s' % (os.getpid(), time.time(), msg))
            sys.stdout.flush()

    def _app_check(self):
        if self._app_cfg is None:
            raise RuntimeError('cfg not defined')

    def _app_node_init(self):
        # 先验证节点是否启动
        my_id = self._app_cfg['substrate']['id']

        if os.getenv("DOCKER_MODE") == "True":
            self._app_docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
            self.prometheus_host = self._app_cfg['substrate']['id']
        else:
            self._app_docker_client = docker.from_env()

        self._debug = self._app_cfg['global']['debug']

        self._app_status['id'] = my_id
        self._app_status['status'] = 'booting'
        self._app_status['heartbeat'] = int(time.time())
        self._app_session_name = "glue_%s" % self._app_cfg['substrate']['id']
        self._app_session_key = self._app_cfg['global']['session_key']

    def _app_docker_pull_image(self, image):
        dc = self._app_docker_client
        try:
            dc.images.get(image)
        except docker_errors.ImageNotFound:
            self._d('Download %s' % image)
            dc.images.pull(image)

    def _app_stop_container(self, timeout=30, force=False):
        # self._app_change_status('stopping')
        d = self._d
        if self._app_is_container_running() and self._app_docker_instance:
            d('容器在运行')
            if force:
                d('强制关闭，kill容器')
                self._app_docker_instance.kill()
            else:
                self._app_docker_instance.stop()
                if not self._app_waiting_container_offline(timeout=timeout):
                    d('关闭等待超时，强制关闭')
                    self._app_stop_container(force=True)
        if self._app_docker_instance:
            self._app_waiting_container_offline()
            d('移除容器')
            self._app_docker_instance.remove()
            self._app_docker_instance = None

    def _app_waiting_container_offline(self, retry=3, timeout=30):
        _try = 0
        if self._app_docker_instance:
            while _try < retry:
                try:
                    self._d('第%d次等待关闭' % (_try + 1))
                    rt = self._app_docker_instance.wait(
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

    def _app_start_container(self, validator=False):
        image = self._app_cfg['substrate']['image']
        self._app_docker_pull_image(image)
        self._app_add_network()

        name = self._app_cfg['substrate']['id']
        name_str = '--name %s' % name

        base_path = dict()
        _path = self._app_cfg['substrate']['base_path']
        base_path[_path] = {'bind': _path, 'mode': 'rw'}
        base_path_str = "--base-path %s" % _path

        _port = self._app_cfg['substrate']['port']
        ports = dict()
        ports['9944/tcp'] = 9944
        ports['9615/tcp'] = 9615
        ports['%d/tcp' % _port] = _port
        port_str = '--port %s' % _port

        boot_nodes = ""
        if len(self._app_cfg['substrate']['boot_nodes']) > 0:
            boot_nodes = "--bootnodes %s" % " ".join(self._app_cfg['substrate']['boot_nodes'])

        identity_key = ""
        if len(self._app_cfg['substrate']['node_key']) > 0:
            identity_key = "--node-key %s" % self._app_cfg['substrate']['node_key']

        command = "{base_path} {port} {name} --rpc-cors=all {boot_nodes} {identity_key} --prometheus-external".format(
            base_path=base_path_str,
            port=port_str,
            name=name_str,
            boot_nodes=boot_nodes,
            identity_key=identity_key,
        )

        if validator:
            command = command + " --validator"
        else:
            # --rpc-external and --ws-external options shouldn\'t be used if the node is running as a validator.
            # Use `--unsafe-rpc-external` if you understand the risks.
            command = command + " --rpc-external --ws-external"

        self._app_docker_instance = self._app_docker_client.containers.run(
            image=image,
            name=name,
            ports=ports,
            volumes=base_path,
            command=command,
            detach=True,
            network='substrate-ops'
        )

    def _app_is_container_running(self):
        if self._app_docker_instance is None:
            c_name = self._app_cfg['substrate']['id']
            try:
                self._app_docker_instance = self._app_docker_client.containers.get(c_name)
                return self._app_docker_instance.status == 'running'
            except docker_errors.NotFound:
                return False
        self._app_docker_instance.reload()
        return self._app_docker_instance.status == 'running'

    def _app_is_validator_working(self):
        try:
            url = "http://{prometheus}:9615/metrics".format(prometheus=self.prometheus_host)
            metrics = requests.get(url).text.split("\n")
            current = 0
            for index, v in enumerate(metrics):
                metric = v.split(" ")
                if metric[0] == 'darwinia_block_height{status="best"}':
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
        print('%s收到退出请求' % os.getpid())
        sys.stdout.flush()
        if self._app_docker_instance:
            self._app_stop_container()

        raise SystemExit(0)

    def run(self):
        signal.signal(signal.SIGTERM, self.terminate)
        d = self._d
        d('初始化启动')
        self._app_check()
        self._app_node_init()

        try:
            while True:
                d('同步节点状态')
                if self._app_is_container_running():
                    if not self._app_is_validator_working():
                        d('节点同步不正常')
                        self._app_stop_container()
                    else:
                        d('节点同步正常！！！')
                else:
                    d('container start')
                    self._app_start_container(self._app_cfg['substrate']['validator'])
                    d('container start success')
                time.sleep(50)
        except Exception as e:
            print(e)
            time.sleep(10)
            raise e
