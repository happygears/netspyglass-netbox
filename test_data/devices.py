from test_data.netbox_models import netbox_url

dev1 = {
    "id": 1,
    "url": f'{netbox_url}/api/dcim/devices/1/',
    "display": "device 1",
    "name": "dev1",
    "device_type": {
        "id": 1,
        "url": f'{netbox_url}/api/dcim/device-types/1/',
        "display": "QFX10008",
        "manufacturer": {
            "id": 1,
            "url": f'{netbox_url}/api/dcim/manufacturers/1/',
            "display": "Juniper",
            "name": "Juniper",
            "slug": "juniper",
            "description": ""
        },
        "model": "QFX10008",
        "description": ""
    },
    "serial": "DH996-1",
    "site": {
        "id": 1,
        "display": "site 1",
        "name": "site-1"
    },
    "role": {'description': '', 'display': 'server', 'id': 6, 'name': 'server', 'slug': 'server',
             'url': f'{netbox_url}/api/dcim/device-roles/6/'},
    "latitude": 52.00,
    "longitude": 4.00,
    "status": {
        "value": "active"
    },
    "primary_ip": {
        "id": 2,
        "display": "11.11.11.11/32",
        "family": {
            "value": 4,
            "label": "IPv4"
        },
        "address": "11.11.11.11/32",
        "description": ""
    },
    "interface_count": 1,
    "tags": [{'id': 1, 'url': f'{netbox_url}/api/extras/tags/1/', 'display': 'physical', 'name': 'physical',
              'slug': 'physical', 'color': 'ffc107'},
             {'id': 2, 'url': f'{netbox_url}/api/extras/tags/2/', 'display': 'pop', 'name': 'pop', 'slug': 'pop',
              'color': '9e9e9e'}],
    "moc_ip": "11.11.11.11"
}
dev2 = {
    "id": 2,
    "url": f'{netbox_url}/api/dcim/devices/2/',
    "display": "device 2",
    "name": "dev2",
    "device_type": {
        "id": 1,
        "display": "t2",
        "manufacturer": {
            "id": 2,
            "display": "Cisco",
            "name": "Cisco",
            "description": ""
        },
        "model": "AA2",
        "description": ""
    },
    "serial": "a22a",
    "site": {
        "id": 100,
        "display": "site 2",
        "name": "site-2"
    },
    "primary_ip": None,
    "latitude": None,
    "longitude": None,
    "status": {
        "value": "staged"
    },
    "interface_count": 1,
    "moc_ip": "22.22.22.22"
}
dev3 = {
    "id": 3,
    "url": f'{netbox_url}/api/dcim/devices/3/',
    "display": "device 3",
    "name": "dev3",
    "device_type": {
        "id": 1,
        "display": "QFX2000",
        "manufacturer": {
            "id": 3,
            "name": "Dell",
            "description": ""
        },
        "model": "QFX2000",
        "slug": "dell-qfx2000",
        "description": ""
    },
    "serial": "dh226-2",
    "site": {
        "id": 2,
        "display": "site 3",
        "name": "site-3"
    },
    "primary_ip": None,
    "latitude": 12.00,
    "longitude": 14.00,
    "status": {
        "value": "offline"
    },
    "interface_count": 1,
    "moc_ip": "33.33.33.33"
}

nsg1 = {"name": dev1.get("name"),
        "address": dev1.get("moc_ip"),
        "id": 1,
        "polling": "v2ro",
        "tags": ["Site.site-1", "Monitor.ALERTED", "Model.qfx10008",
                 "Vendor.Juniper", "SerialNumber.DH996-1", "Role.PHYSICAL", "Role.POP"]
        }
nsg2 = {"name": dev2.get("name"),
        "address": dev2.get("moc_ip"),
        "id": 2,
        "polling": "v2ro",
        "tags": ["Site.site-2", "Monitor.IGNORED", "Model.aa2",
                 "Vendor.Cisco", "SerialNumber.A22A"]
        }
nsg3 = {"name": dev3.get("name"),
        "address": dev3.get("moc_ip"),
        "id": 3,
        "polling": "v2ro",
        "tags": ["Site.site-3", "Monitor.IGNORED", "Model.qfx2000",
                 "Vendor.Dell", "SerialNumber.DH226-2"]
        }

netbox_devises_response = {
    "count": 0,
    "next": None,
    "previous": None,
    "results": []
}

nsg_devices_response = {
    'id': 'a',
    'rows': [],
    'dataFreshness': 0,
    'server': 'nsg-api-1',
    'queryId': 1731483277664,
    'age': 0}
