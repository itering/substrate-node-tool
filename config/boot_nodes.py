import requests
from multiprocessing.dummy import Pool
from multiprocessing import Queue
import threading


class Boot:
    def __init__(self):
        self.queue = Queue()
        self.urls = []
        self.network = ""
        self.pool = None

        self.network_dict = {
            "": "Crab",
            "kusama": "Kusama",
            "polkadot": "Polkadot CC1",
            "edgeware": "Edgeware",
            "darwinia": "Crab"
        }

    def run(self, network):
        self.pool = Pool(30)
        self.network = network
        t = threading.Thread()
        t.setDaemon(True)
        t.start()

        self.pool.map(self._put_queue, list(range(0, 20)))
        while self.queue.empty() is False:
            node_id = self.queue.get()
            self.pool.map_async(self._get_url, [node_id])
        self.pool.close()
        self.pool.join()
        return self.urls

    def _put_queue(self, node_id):
        self.queue.put(node_id)

    def _get_url(self, node_id):
        c = requests.get(
            url="https://telemetry.polkadot.io/network_state/%s/%d" % (self.network_dict[self.network], node_id),
            timeout=3)
        if c.content == b'Node has disconnected or has not submitted its network state yet':
            return
        j = c.json()
        address = list(filter(lambda x:
                              x[5:].startswith("10") is False and
                              x[5:].startswith("172") is False and
                              x[5:].startswith("127") is False,
                              j['externalAddresses']))
        if len(address) > 0:
            boot_node = "{}/p2p/{}".format(address[0], j['peerId'])
            self.urls.append(boot_node)
