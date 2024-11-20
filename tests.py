import argparse
import unittest
from unittest import mock
from urllib.parse import urlparse
from os import path
import json
from test_data.devices import dev1, dev2, dev3, netbox_devises_response, nsg1, nsg2, nsg3, nsg_devices_response

from nsg_netbox import NsgNetboxIntegration

dns = {}
Netbox_devices = []
NSG_devices = []
NSG_tags = {}

env = {"netbox_token": "1111",
       "netbox_url": "https://netbox.net",
       "nsg_url": "https://nsg.net",
       "nsg_token": "2222",
       "netid": "1",
       "channel": None,
       "interval": 10000
       }

idx = {
    1: nsg1, '11.11.11.11': nsg1,
    2: nsg2, '22.22.22.22': nsg2,
    3: nsg3, '33.33.33.33': nsg3
}


def mock_request_get(*args, **kwargs):
    url = kwargs.get("url") or args[0]
    url = urlparse(url)
    if url.netloc == "netbox.net":
        if url.path == "/api/status":
            return MockResponse(200, {"netbox-version": "4.0.1"})
        if url.path == "/api/dcim/devices/":
            netbox_devises_response["results"] = Netbox_devices
            return MockResponse(200, netbox_devises_response)
    if url.netloc == "nsg.net":
        if url.path == "/v2/ui/net/1/tasks/":
            return MockResponse(200, [])
        if url.path == "/v2/tags/net/1/external/":
            res = []
            for id, dev in NSG_tags.items():
                for tag in dev.get("tags"):
                    res.append({'category': 'device',
                                'device': {'address': dev.get('address'), 'id': dev.get('id'), 'name': dev.get('name')},
                                "tags": [tag]})
            return MockResponse(200, res)


def mock_request_post(*args, **kwargs):
    url = kwargs.get("url") or args[0]
    url = urlparse(url)
    global NSG_devices, NSG_tags
    if url.netloc == "nsg.net":
        if url.path == "/v2/query/net/1/data":
            rows = []
            for dev in NSG_devices:
                rows.append({'id': dev.get("id"), 'name': dev.get("name"), 'address': dev.get("address")})
            result = nsg_devices_response.copy()
            result["rows"] = rows
            return MockResponse(200, [result, ])
        if url.path == "/v2/ui/net/1/devices/":
            data = kwargs.get("json")
            for dev in data:
                id_ = idx.get(dev.get("address"), {}).get("id")
                if id_:
                    NSG_devices.append({**dev, "id": id_, "tags": []})
            return MockResponse(200, [])
        if url.path == "/v2/tags/net/1/external/":
            data = kwargs.get("json")
            for dev in data:
                if dev.get("category") == "device":
                    id_ = dev.get("device", {}).get("id")
                    if not id_:
                        address = dev.get("device", {}).get("address")
                        id_ = idx.get(address, {}).get("id")
                    if dev.get("tags"):
                        NSG_tags[id_] = {**idx.get(id_), "tags": dev.get("tags")}
                    else:
                        del NSG_tags[id_]
            return MockResponse(200, [])


def mock_request_delete(*args, **kwargs):
    url = kwargs.get("url") or args[0]
    url = urlparse(url)
    if url.netloc == "nsg.net":
        if url.path.startswith('/v2/ui/net/1/devices'):
            global NSG_devices
            _, ids = url.path.rsplit('/', maxsplit=1)
            for id in ids.split(','):
                id = int(id)
                NSG_devices = [x for x in NSG_devices if x.get("id") != id]
            return MockResponse(200, [])


def dns_request(*args, **kwargs):
    if args[0] == 'dev1.test.com':
        return "11.11.11.11"
    if args[0] == 'dev2.test.com':
        return "22.22.22.22"
    if args[0] == 'dev3.test.com':
        return "33.33.33.33"


class MockResponse:
    def __init__(self, status_code: int, data: list or dict = {}):
        self.headers = {'Nsg-Server': 'server1'}
        self.json_data = data
        self.status_code = status_code
        self.ok = True

    def json(self) -> list or dict:
        return self.json_data

    def text(self) -> str:
        return json.dumps(self.json_data)


def check_devices():
    for dev in Netbox_devices:
        addr = dev.get("moc_ip")
        exp = idx.get(addr)
        assert exp
        for d in NSG_devices:
            if d == {**exp, "tags": []} or d == exp:
                break
        else:
            assert False, f"{dev.get('name')} not in NSG devices"


class TestNetboxDevices(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        global dns
        cls.nbox_nsg = cls.get_nsgNetbox()
        domain = cls.nbox_nsg.config.get("domain")
        dns = {f"{dev1.get('name')}": dev1.get("moc_ip"),
               dev2.get('name'): dev2.get("moc_ip"),
               f"{dev3.get('name')}.{domain}": dev3.get("moc_ip")
               }

    def setUp(self) -> None:
        global NSG_devices, Netbox_devices, NSG_tags
        Netbox_devices = []
        NSG_devices = []
        NSG_tags = {}

    @mock.patch('requests.get', side_effect=mock_request_get)
    def get_nsgNetbox(self, *args):
        pa = argparse.Namespace(**env,
                                config=path.join(path.dirname(__file__), "test_data", "test_config.yaml"),
                                )
        nbox_nsg = NsgNetboxIntegration(pa)
        return nbox_nsg


    @mock.patch('requests.get', side_effect=mock_request_get)
    @mock.patch('requests.sessions.Session.get', side_effect=mock_request_get)
    @mock.patch('requests.sessions.Session.post', side_effect=mock_request_post)
    @mock.patch('requests.sessions.Session.delete', side_effect=mock_request_delete)
    @mock.patch('requests.post', side_effect=mock_request_get)
    @mock.patch('socket.gethostbyname', side_effect=dns_request)
    def test_add_new_devices(self, *args):
        global Netbox_devices, NSG_devices, NSG_tags
        Netbox_devices = [dev2, dev3]
        self.nbox_nsg.run()
        assert len(NSG_devices) == 2
        check_devices()
        assert NSG_tags[2]["tags"] == nsg2["tags"]
        assert NSG_tags[3]["tags"] == nsg3["tags"]

        #  second run. check no duplicates
        self.nbox_nsg.run()
        assert len(NSG_devices) == 2
        check_devices()
        assert NSG_tags[2]["tags"] == nsg2["tags"]
        assert NSG_tags[3]["tags"] == nsg3["tags"]

        # two devices in Netbox
        Netbox_devices.append(dev1)
        self.nbox_nsg.run()

        assert len(NSG_devices) == 3
        check_devices()
        assert NSG_tags[1]["tags"] == nsg1["tags"]
        assert NSG_tags[2]["tags"] == nsg2["tags"]
        assert NSG_tags[3]["tags"] == nsg3["tags"]

    @mock.patch('requests.get', side_effect=mock_request_get)
    @mock.patch('requests.sessions.Session.get', side_effect=mock_request_get)
    @mock.patch('requests.sessions.Session.post', side_effect=mock_request_post)
    @mock.patch('requests.sessions.Session.delete', side_effect=mock_request_delete)
    @mock.patch('requests.post', side_effect=mock_request_get)
    @mock.patch('socket.gethostbyname', side_effect=dns_request)
    def test_devices_deleted_from_netbox(self, *args):
        global Netbox_devices, NSG_devices, NSG_tags
        #  one device in netbox: dev2
        #  three devices in nsg: dev1, dev2, dev3
        Netbox_devices = [dev1, dev2]
        NSG_devices = [nsg1, nsg2, nsg3]
        NSG_tags = {1: nsg1, 2: nsg2, 3: nsg3}
        self.nbox_nsg.run()
        assert len(NSG_devices) == 2, "dev3 has not deleted"
        check_devices()
        assert NSG_tags[1]["tags"] == nsg1["tags"],\
            f"dev2 tags not equal actual: {NSG_tags[1]['tags']} expected: {nsg1['tags']}"
        assert NSG_tags[2]["tags"] == nsg2["tags"],\
            f"dev2 tags not equal actual: {NSG_tags[2]['tags']} expected: {nsg2['tags']}"
        assert not NSG_tags.get(3), "tags of dev3 not deleted"

        # no devices in Netbox
        Netbox_devices = []
        self.nbox_nsg.run()
        assert len(NSG_devices) == 0, "dev1, dev2 have not deleted"
        assert len(NSG_tags) == 0, "tags have not deleted"

    @mock.patch('requests.get', side_effect=mock_request_get)
    @mock.patch('requests.sessions.Session.get', side_effect=mock_request_get)
    @mock.patch('requests.sessions.Session.post', side_effect=mock_request_post)
    @mock.patch('requests.sessions.Session.delete', side_effect=mock_request_delete)
    @mock.patch('requests.post', side_effect=mock_request_get)
    @mock.patch('socket.gethostbyname', side_effect=dns_request)
    def test_device_tag_chenged(self, *args):
        global Netbox_devices, NSG_devices, NSG_tags
        dev3new = {**dev3, "status": {"value": "active"}}
        dev2new = {**dev2, "status": {"value": "active"}, "serial": "00000"}
        Netbox_devices = [dev1, dev2new, dev3new]
        NSG_devices = [nsg1, nsg2, nsg3]
        NSG_tags = {1: nsg1, 2: nsg2, 3: nsg3}
        self.nbox_nsg.run()
        assert NSG_tags[1]["tags"] == nsg1["tags"],\
            f"dev1 tags not equal actual: {NSG_tags[2]['tags']} expected: {nsg2['tags']}"
        new_tags = ["Site.site-2", "Monitor.ALERTED", "Model.aa2",
                    "Vendor.Cisco", "SerialNumber.00000"]
        assert NSG_tags[2]["tags"] == new_tags, \
            f"dev1 tags not equal actual: {NSG_tags[2]['tags']} expected: {new_tags}"
        new_tags = ["Site.site-3", "Monitor.ALERTED", "Model.qfx2000",
                    "Vendor.Dell", "SerialNumber.DH226-2"]
        assert NSG_tags[3]["tags"] == new_tags, \
            f"dev1 tags not equal actual: {NSG_tags[3]['tags']} expected: {new_tags}"


    @mock.patch('requests.get', side_effect=mock_request_get)
    @mock.patch('requests.sessions.Session.get', side_effect=mock_request_get)
    @mock.patch('requests.sessions.Session.post', side_effect=mock_request_post)
    @mock.patch('requests.sessions.Session.delete', side_effect=mock_request_delete)
    @mock.patch('requests.post', side_effect=mock_request_get)
    @mock.patch('socket.gethostbyname', side_effect=dns_request)
    def test_tag_list_changed(self, *args):
        global Netbox_devices, NSG_devices, NSG_tags
        # update config with new tags
        pa = argparse.Namespace(**env,
                                config=path.join(path.dirname(__file__), "test_data", "test_config_less_tags.yaml"))
        self.nbox_nsg = NsgNetboxIntegration(pa)

        Netbox_devices = [dev1, dev2, dev3]
        NSG_devices = [nsg1, nsg2, nsg3]
        NSG_tags = {1: nsg1, 2: nsg2, 3: nsg3}
        self.nbox_nsg.run()

        assert NSG_tags[1]["tags"] == ['Site.site-1', 'Monitor.ALERTED', 'Lat.52.0', 'Lon.4.0'],\
            f"dev1 tags not updated"
        #  dev2 does not have latitude and longitude
        assert NSG_tags[2]["tags"] == ['Site.site-2', 'Monitor.IGNORED'], f"dev2 tags not updated"
        assert NSG_tags[3]["tags"] == ['Site.site-3', 'Monitor.IGNORED', 'Lat.12.0', 'Lon.14.0'],\
            f"dev3 tags not updated"

        self.nbox_nsg = self.get_nsgNetbox()


if __name__ == '__main__':
    unittest.main()