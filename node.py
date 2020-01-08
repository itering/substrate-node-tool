#!/usr/bin/env python
# encoding: utf-8

import os
import sys
import docker
import multiprocessing
import time
from libs import consul, daemon
import signal
from docker import errors as docker_errors
from requests.exceptions import ReadTimeout
import requests

node_status = ["stop", "booting", "starting", "stopping", "running", "failed"]


class Monitor(multiprocessing.Process):
    _app_cfg = None
    _app_docker_client = None
    _app_docker_instance = None
    _app_consul = None
    _app_status = {
        "id": None,
        "status": "stop",
        "heartbeat": 0,
        # "docker": {
        #     "image": None,
        #     "status": None,
        #     "retry": []
        # }
    }
    # 全局的session key
    _app_session_key = None
    # 当前的节点的session名称
    _app_session_name = None
    # 使用session请求的session ID
    _app_session_id = None
    _app_leader = {}
    _app_peers = []

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
        client = self._app_cfg['consul']['client']
        port = self._app_cfg['consul']['port']
        self._app_consul = consul.ConsulClient(client, port)

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
        if self._app_consul is None:
            raise RuntimeError('consul client not instantiation')

    def _app_node_init(self):
        # 先验证节点是否启动
        my_id = self._app_cfg['substrate']['id']
        status = self._app_consul.load_kv(my_id)
        if type(status) == dict and 'status' in status and status['status'] not in ['stop', 'failed']:
            raise RuntimeError("%s status not in [stop | failed]" % status['status'])
        base_path = self._app_cfg['substrate']['base_path']
        if not os.path.exists(base_path):
            os.makedirs(base_path)
        if os.getenv("DOCKER_MODE") == "True":
            self._app_docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
        else:
            self._app_docker_client = docker.from_env()
        self._debug = self._app_cfg['global']['debug']
        # self._app_status['active'] = True
        self._app_status['id'] = my_id
        # self._app_status['ip'] = self._app_cfg['consul']['bind']
        self._app_status['status'] = 'booting'
        self._app_status['heartbeat'] = int(time.time())
        self._app_session_name = "glue_%s" % self._app_cfg['substrate']['id']
        self._app_session_key = self._app_cfg['global']['session_key']
        if not self._app_sync_status_to_kv():
            raise RuntimeError('Failed to save status to consul KV')

    def _app_sync_status_to_kv(self):
        key = self._app_cfg['substrate']['id']
        return self._app_consul.save_kv(key, self._app_status)

    def _app_sync_status_from_kv(self):
        key = self._app_cfg['substrate']['id']
        status = self._app_consul.load_kv(key)
        if status:
            self._app_status = status
        peers = self._app_consul.get_peers()
        if peers:
            self._app_peers = peers

    def _app_change_status(self, status):
        if status not in node_status:
            self._d('%s not in %s' % (status, node_status))
            return False
        self._app_status['status'] = status
        return self._app_sync_status_to_kv()

    def _app_node_active(self, active=True):
        self._app_sync_status_from_kv()
        self._app_status['active'] = active
        return self._app_sync_status_to_kv()

    def _app_node_inactive(self):
        return self._app_node_active(False)

    def _app_is_leader(self):
        self._app_has_leader()
        my_id = self._app_cfg['substrate']['id']
        # print("leader: %s" % self._app_leader)
        if self._app_leader:
            return self._app_leader['leader']['id'] == my_id
        return False

    def _app_has_leader(self):
        leader = self._app_consul.get_kv_leader(self._app_session_key)
        if leader:
            self._app_leader = leader
            self._d('有leader')
            return True
        return False

    def _app_release_leader(self):
        if self._app_session_id is not None:
            self._app_consul.destroy_session(self._app_session_id)
            self._app_session_id = None

    def _app_election_leader(self, waiting: int):
        d = self._d
        waiting += 15
        d('开始选举, 将当前session_id置空')
        self._app_session_id = None
        # 1. 先创建一个session
        cc = self._app_consul
        d("创建一个新session")
        session_id = cc.create_session(
            session_name=self._app_session_name,
            ttl='%ds' % waiting
        )
        d("sessionId: %s" % session_id)
        if session_id is None:
            return False
        # 2. 尝试使用这个session去锁定session_key
        d('尝试锁定')
        is_leader = cc.acquire_kv(
            self._app_session_key,
            session_id,
            self._app_status
        )
        d('是否锁定: %s' % is_leader)
        if is_leader:
            d('当前sessionId: %s' % session_id)
            self._app_session_id = session_id
        else:
            # 锁定失败，移除session
            d('锁定失败，移除session')
            cc.destroy_session(session_id)
        return is_leader

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

    def _app_start_as_validator(self):
        if self._app_docker_instance:
            self._app_stop_container()
        return self._app_start_container(validator=True)

    def _app_start_as_follower(self):
        if self._app_docker_instance:
            self._app_stop_container()
        return self._app_start_container()

    def _app_is_validator(self):
        attrs = self._app_docker_instance.attrs
        if '--validator' in attrs['Args']:
            return True
        return False

    def _app_waiting_container_online(self):
        self._d('阻塞获取状态')
        if self._app_docker_instance:
            _c = 0
            while _c < 30:
                self._app_docker_instance.reload()
                if self._app_docker_instance.status == 'running':
                    return True
                time.sleep(1)
        return False

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

    def _app_start_container(self, validator=False):
        image = self._app_cfg['substrate']['image']
        self._app_docker_pull_image(image)

        name = self._app_cfg['substrate']['id']
        name_str = '--name %s' % name

        telemetry_url = "--telemetry-url ws://%s/socket/%s" % (
            str(self._app_cfg['substrate']['monitor_host']).rstrip('/'),
            self._app_cfg['substrate']['id']
        )
        for _t in self._app_cfg['substrate']['telemetry_url']:
            telemetry_url += " %s" % _t

        base_path = dict()
        _path = self._app_cfg['substrate']['base_path']
        base_path[_path] = {'bind': _path, 'mode': 'rw'}
        base_path_str = "--base-path %s" % _path

        _port = self._app_cfg['substrate']['port']
        ports = dict()
        ports['9944/tcp'] = 9944
        ports['%d/tcp' % _port] = _port
        port_str = '--port %s' % _port

        boot_nodes = ""
        if len(self._app_cfg['substrate']['boot_nodes']) > 0:
            boot_nodes = "--bootnodes %s" % " ".join(self._app_cfg['substrate']['boot_nodes'])

        identity_key = ""
        if len(self._app_cfg['substrate']['node_key']) > 0:
            identity_key = "--node-key %s" % self._app_cfg['substrate']['node_key']

        command = "{base_path} {port} {name} --rpc-cors=all --{telemetry_url} {boot_nodes} {identity_key}".format(
            base_path=base_path_str,
            port=port_str,
            name=name_str,
            telemetry_url=telemetry_url,
            boot_nodes=boot_nodes,
            identity_key=identity_key,
        )

        if validator:
            command = command + " --validator"
        else:
            # --rpc-external and --ws-external options shouldn\'t be used if the node is running as a validator.
            # Use `--unsafe-rpc-external` if you understand the risks.
            command = command + "--rpc-external --ws-external"
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

    # def _app_get_node_id(self, ip):
    #     self._app_check()
    #     all_server = self._app_consul.get_peers()
    #     if ip not in all_server:
    #         return RuntimeError("%s not in consul peers")
    #     node = self._app_consul.load_kv(ip)
    #     if node is None:
    #         raise RuntimeError("%s have not status, maybe glue not start")
    #     return node['id']

    def _app_heartbeat(self):
        # 心跳监控，将自己状态写入KV
        # 检查出块状态
        # 检查他人状态
        # print('[%s] 当前Leader: %s' % (os.getpid(), self._app_consul.get_leader()))
        # sys.stdout.flush()
        self._app_status['heartbeat'] = int(time.time())
        if self._app_session_id is not None:
            self._d("有session_id: %s, renew session" % self._app_session_id)
            self._app_consul.renew_session(self._app_session_id)
        self._app_sync_status_to_kv()

    def _app_is_node_stop(self):
        return self._app_status['status'] == 'stop'

    def _app_is_node_failed(self):
        return self._app_status['status'] == 'failed'

    def _app_is_node_running(self):
        return self._app_status['status'] == 'running'

    def _app_is_validator_working(self):
        return self._waiting_validator_connect_monitor()

    def _waiting_validator_connect_monitor(self):
        try_count = 0
        while True:
            try:
                url = 'http://' + str(self._app_cfg['substrate']['monitor_host']).rstrip('/') + "/api/node/status"
                status = requests.get(url).json()['data']
                if self._app_status['id'] in status and status[self._app_status['id']]['sync_status']:
                    return status[self._app_status['id']]['sync_status']
                else:
                    try_count += 1
                    if try_count > 3:
                        return False
                    time.sleep(1)
            except requests.exceptions.ConnectionError:
                return False

    def terminate(self, *args, **kwargs):
        # 关闭时候需要的执行步骤，把自己出服务列表
        print('%s收到退出请求' % os.getpid())
        sys.stdout.flush()
        self._app_change_status('stop')
        if self._app_docker_instance:
            self._app_stop_container()
        self._app_release_leader()
        raise SystemExit(0)

    def run(self):
        signal.signal(signal.SIGTERM, self.terminate)
        d = self._d
        d('初始化启动')
        self._app_check()
        self._app_node_init()
        self._app_change_status('running')
        # 等待1秒
        time.sleep(1)
        # 检查session锁
        try:
            validator_waiting = self.cfg['substrate']['validator_waiting']
        except KeyError:
            validator_waiting = 120
        try:
            while True:
                d('同步节点状态')
                self._app_sync_status_from_kv()
                d('如果节点状态为stop或者failed则不更新心跳')
                if not self._app_is_node_stop() and not self._app_is_node_failed():
                    d('看看当前有没有leader， 如果当前为running状态就去抢leader')
                    if not self._app_has_leader() and self._app_is_node_running():
                        d('参与选举leader，然后等待1秒')
                        self._app_election_leader(validator_waiting)
                        time.sleep(1)
                    d('检查是不是leader')
                    if self._app_is_leader():

                        d('是leader， 检查容器是不是在运行')
                        if self._app_is_container_running():
                            d('已经在运行了，检查是不是验证节点')
                            if self._app_is_validator():
                                d('是验证人节点，检查产块是否正常')
                                if not self._app_is_validator_working():
                                    d('产块不正常，关闭节点')
                                    self._app_stop_container()
                                    d('等待容器关闭')
                                    if not self._app_waiting_container_offline():
                                        self._app_stop_container(force=True)
                                    d('释放leader')
                                    self._app_release_leader()
                                    d('等待5秒让别人去抢')
                                    time.sleep(5)
                                    d("返回循环顶部")
                                    continue
                            else:
                                d('不是验证人节点，停止原来的容器，拉起验证人')
                                self._app_stop_container()
                                d('等待容器关闭')
                                if not self._app_waiting_container_offline():
                                    self._app_stop_container(force=True)
                                d('拉起验证人')
                                self._app_start_as_validator()
                                # # todo 启动3次，3次失败标记自己为失败的节点，退出竞选
                                d('检查容器是否running')
                                if not self._app_waiting_container_online():
                                    d('容器启动失败了，强制停止容器')
                                    self._app_stop_container(force=True)
                                    d('更改自己状态为failed')
                                    self._app_change_status('failed')
                                    d('释放leader')
                                    self._app_release_leader()
                                else:
                                    d('启动时候需要一定时间来恢复产块，等待%d秒' % validator_waiting)
                                    time.sleep(validator_waiting)
                        else:
                            # 没有运行，启动验证人节点
                            d('没有运行，启动验证人节点')
                            self._app_start_as_validator()
                            # todo 启动3次，3次失败标记自己为失败的节点，退出竞选
                            d('检查容器是否running')
                            d('检查容器是否running')
                            if not self._app_waiting_container_online():
                                d('容器启动失败了，强制停止容器')
                                self._app_stop_container(force=True)
                                d('更改自己状态为failed')
                                self._app_change_status('failed')
                                d('释放leader')
                                self._app_release_leader()
                            else:
                                # 启动时候需要一定时间来恢复产块
                                d('启动时候需要一定时间来恢复产块，等待%d秒' % validator_waiting)
                                time.sleep(validator_waiting)
                    else:
                        d('不是Leader，检查容器是不是follower, 检查是不是启动了镜像，置空session_id')
                        self._app_session_id = None
                        if self._app_is_container_running():
                            d('启动着，看下是不是follower节点')
                            if self._app_is_validator():
                                d('当前不是Leader，但是启动着validator节点，开始关闭validator节点')
                                self._app_stop_container()
                                # todo 应该加点什么判断
                                d('启动follower节点')
                                self._app_start_as_follower()
                                # todo 启动3次，3次失败标记自己为失败的节点，退出竞选
                                d('检查容器是否running')
                                if not self._app_waiting_container_online():
                                    d('容器启动失败了，强制停止容器')
                                    self._app_stop_container(force=True)
                                    d('更改自己状态为failed')
                                    self._app_change_status('failed')
                        else:
                            d('没启动，启动follower节点')
                            self._app_start_as_follower()
                            # todo 启动3次，3次失败标记自己为失败的节点，退出竞选
                            d('检查容器是否running')
                            if not self._app_waiting_container_online():
                                d('容器启动失败了，强制停止容器')
                                self._app_stop_container(force=True)
                                d('更改自己状态为failed')
                                self._app_change_status('failed')
                    d('写心跳')
                    self._app_heartbeat()
                else:
                    d('节点状态为stop或者failed, 检查是不是leader，是leader需要是释放')
                    if self._app_is_leader():
                        d('有灾难发生了，有异常，需要释放leader, 检查容器有没有启动')
                        if self._app_is_container_running():
                            d('启动着，关了')
                            self._app_stop_container()
                        d('释放leader')
                        self._app_release_leader()
                    else:
                        d('不是leader，检查容器是否允许')
                        if self._app_is_container_running():
                            d('启动着，关了')
                            self._app_stop_container()
                d('逻辑跑完，躺3秒')
                time.sleep(3)
        except Exception as e:
            self._app_change_status('failed')
            raise e
