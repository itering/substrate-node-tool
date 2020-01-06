#!/usr/bin/env python
# encoding: utf-8

import requests
import json
from base64 import b64decode


class ConsulClient(object):
    _api_ver = 'v1'

    def __init__(self, ip, port=8500):
        self._set_api_url(ip, port)

    def _set_api_url(self, ip, port):
        if ip == '0.0.0.0':
            ip = '127.0.0.1'
        port = str(port)
        url = "http://%s:%s" % (ip, port)
        self._url = str(url).rstrip('/') + '/' + self._api_ver

    def _get_api_url(self, api=None):
        if api is None:
            return self._url
        return self._url + '/' + str(api).lstrip('/')

    def _get(self, api, params=None, **kwargs):
        url = self._get_api_url(api)
        r = requests.get(url, params=params, **kwargs)
        if r.status_code == requests.codes.ok:
            return r.text
        return None

    def _put(self, api, json_data=None, **kwargs):
        url = self._get_api_url(api)
        r = requests.put(url, json=json_data, **kwargs)
        if r.status_code == requests.codes.ok:
            return r.text
        return None

    def _delete(self, api, **kwargs):
        url = self._get_api_url(api)
        r = requests.delete(url, **kwargs)
        if r.status_code == requests.codes.ok:
            return r.text
        return None

    def load_kv(self, key):
        rt = self._get('/kv/' + str(key))
        try:
            rt = json.loads(rt)
            val = rt[0]['Value']
            val = b64decode(val).decode()
        except (TypeError, IndexError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return json.loads(val)

    def save_kv(self, key, val):
        rt = self._put('/kv/' + str(key), json_data=val)
        if rt in ['true', b'true']:
            return True
        return False

    def delete_kv(self, key):
        rt = self._delete('/kv/' + str(key))
        if rt in ['true', b'true']:
            return True
        return False

    def get_kv_leader(self, key):
        if key is None:
            return key
        leader_info = None
        api = '/kv/' + str(key).lstrip('/')
        data = self._get(api)
        try:
            data = json.loads(data)
            data = data[0]
        except (TypeError, IndexError, json.JSONDecodeError):
            return None

        if 'Session' in data:
            try:
                _leader = json.loads(b64decode(data["Value"]))
            except json.JSONDecodeError:
                _leader = b64decode(data["Value"]).decode()

            leader_info = {
                'leader': _leader,
                'session': data["Session"]
            }

        return leader_info

    def get_peers(self):
        api = '/status/peers'
        data = self._get(api)
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
        return [x.split(':')[0] for x in data]

    def create_session(self, session_name, lock_delay="1s", ttl="30s"):
        if session_name is None:
            return None
        api = '/session/create'
        payload = {
            "Name": str(session_name),
            "LockDelay": lock_delay,
            "TTL": ttl
        }
        rt = self._put(api, json_data=payload)
        try:
            return json.loads(rt)['ID']
        except (json.JSONDecodeError, TypeError, IndexError):
            return None

    def destroy_session(self, session_id):
        api = '/session/destroy/' + str(session_id).lstrip('/')
        rt = self._put(api)
        if rt in ['true', b'true']:
            return True
        return False

    def get_session(self, session_id):
        api = '/session/info/' + str(session_id).lstrip('/')
        rt = self._get(api)
        try:
            return json.loads(rt)[0]
        except json.JSONDecodeError:
            return None

    def list_session(self, node=None):
        if node:
            api = '/session/node/' + str(node).lstrip('/')
        else:
            api = '/session/list'
        rt = self._get(api)
        try:
            return json.loads(rt)
        except json.JSONDecodeError:
            return None

    def renew_session(self, session_id):
        api = '/session/renew/' + str(session_id).lstrip('/')
        rt = self._put(api)
        try:
            rt = json.loads(rt)
            return session_id == rt[0]['ID']
        except (json.JSONDecodeError, IndexError, TypeError):
            return False

    def acquire_kv(self, session_key, session_id, payload):
        api = '/kv/' + str(session_key).lstrip('/')
        rt = self._put(api, json_data=payload, params={'acquire': session_id})
        if rt in ['true', b'true']:
            return True
        return False

    def release_kv(self, session_key, session_id):
        api = '/kv/' + str(session_key).lstrip('/')
        rt = self._put(api, params={'release': session_id})
        if rt in ['true', b'true']:
            return True
        return False
