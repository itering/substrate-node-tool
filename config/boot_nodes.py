from websocket import create_connection
import ssl
import json

import requests
from multiprocessing.dummy import Pool
from multiprocessing import Queue
import threading


class Boot:
    def __init__(self):
        self.queue = Queue()
        self.pool = Pool(30)
        self.urls = []
        self.network = ""

        self.network_dict = {
            "": "Darwinia IceFrog Testnet",
            "kusama": "Kusama CC3",
            "darwinia": "Darwinia IceFrog Testnet"
        }

    def run(self, network):
        self.network = network
        ws = create_connection('wss://telemetry.polkadot.io/feed/',
                               sslopt={"cert_reqs": ssl.CERT_NONE,
                                       "check_hostname": False,
                                       "ssl_version": ssl.PROTOCOL_TLSv1})

        subscribe_topic = "subscribe:%s" % self.network_dict[network]
        ws.send(subscribe_topic)
        boot_nodes = []
        block_height = 0
        for i in range(0, 3):
            j = json.loads(ws.recv())
            if j[0] != 0:
                for index in range(len(j)):
                    if j[index] == 1:
                        block_height = j[index + 1][0]
                    elif j[index] == 3:
                        if j[index + 1][4][0] == block_height:
                            boot_nodes.append(j[index + 1][0])

        ws.close()
        t = threading.Thread()
        t.setDaemon(True)
        t.start()

        self.pool.map(self._put_queue, list(boot_nodes))
        while self.queue.empty() is False:
            node_id = self.queue.get()
            self.pool.map_async(self._get_url, [node_id])
        self.pool.close()
        self.pool.join()
        return self.urls

    def _put_queue(self, node_id):
        self.queue.put(node_id)

    def _get_url(self, node_id):
        j = requests.get(
            url="https://telemetry.polkadot.io/network_state/%s/%d" % (self.network_dict[self.network], node_id),
            timeout=3).json()
        address = list(filter(lambda x:
                              x[5:].startswith("10") is False and
                              x[5:].startswith("172") is False and
                              x[5:].startswith("127") is False,
                              j['externalAddresses']))
        if len(address) > 0:
            boot_node = "{}/p2p/{}".format(address[0], j['peerId'])
            self.urls.append(boot_node)
