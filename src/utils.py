import argparse
import os

from src.netbox_client import NboxDevice


def update_from_env(nspace: argparse.Namespace):
    for i in ('NSG_TOKEN', 'NETBOX_URL', 'NETBOX_TOKEN', 'NSG_URL'):
        attr = i.lower()
        if not getattr(nspace, attr):
            setattr(nspace, attr, os.environ.get(i))
    # turn off interface tags harvest, until nsg does not support add interface tags by iface name
    setattr(nspace, "ifaces", False)


def make_add_tag_dict(nbox_devices: dict[str: NboxDevice],
                      nsg_tags: dict[str: any]) -> list[dict[str: any]]:
    """
    Make payload for nsg tags POST request

    :param nbox_devices: list of netbox devices
    :param nsg_tags: list of existing devices tags
    :return:  list of tags to update
    """
    tags = []
    for address, device in nbox_devices.items():
        n_tags = nsg_tags.get(address, {})
        row = {"category": "device",
               "device": {"address": address},
               "tags": []
               }
        if not n_tags \
                or set(n_tags.get("tags", {})).difference(device.nsg_tags):
            #     or [f"{k}.{v}" for k, v in device.nsg_tags.items() if n_tags.get("tags", {}).get(k) != str(v)]:
            # row["tags"] = [f"{k}.{v}" for k, v in device.nsg_tags.items()]
            # if no tags or some tags changed add all tags (nsg api flash out all tags and replaces them with new set)
            row["tags"] = device.nsg_tags
        if row.get("tags"):
            tags.append(row)

        if device.iFaces_tags:
            for iName, iTags in device.iFaces_tags.items():
                row = {"category": "interface", "device": {"address": address},
                       "component": {"name": iName}, "tags": iTags}
                idx = [i for i in iTags if i.lower().startswith("ifindex")]
                try:
                    if idx:
                        _, ifIndex = idx[0].split(".")
                        row["component"]["index"] = int(ifIndex)
                except ValueError as e:
                    logging.error(f"ifIndex tag: {idx} | {e}")
                if row.get("tags"):
                    tags.append(row)
    return tags


def make_remove_tag_dict(nsg_devices: set[str], nsg_tags: dict[str: any]) -> list[dict[str: any]]:
    """
    Make payload for nsg tags POST request

    :param nsg_devices: list of nsg devices to delete
    :param nsg_tags: list of existing devices tags
    :return:  list of devices witch tags to remove
    """
    tags = []
    for ip in nsg_devices:
        if nsg_tags.get(ip):
            row = {"category": "device",
                   "device": {"address": ip},
                   "tags": []
                   }
            tags.append(row)
            iFaces = nsg_tags[ip].get("interfaces")
            device_id = nsg_tags[ip].get("device_id")
            if iFaces and device_id:
                for name, vals in iFaces.items():
                    row = {"category": "interface",
                           "device": {"id": device_id},
                           "component": {"name": name, "index": vals.get("index")},
                           "tags": []
                           }
                    tags.append(row)
    return tags

