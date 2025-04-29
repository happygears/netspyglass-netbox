import http
import logging
from json import JSONDecodeError

import requests
from requests import Session, exceptions


class NboxRecord:
    """
    Generic NetBox record class represents Netbox entity
    """
    __slots__ = ("_record", "_type", "name", "nsg_tags", "id", "device_id")

    def __init__(self, record: dict):
        self._record = record
        url: str = record.get("url")
        if url:
            parts = url.strip("/").rsplit("/", maxsplit=2)
            if len(parts) == 3 and parts[2].isdigit():
                self._type = parts[1].lower()
        else:
            self._type = None
        self.name = record.get("name")
        self.id = record.get("id")
        self.nsg_tags = {}
        self.device_id = record.get("device", {}).get("id")  # if hasattr(record, "device") else None

    def __getattr__(self, item):
        res = self._record.get(item)
        if isinstance(res, dict):
            if len(res) == 0:
                return None
            return NboxRecord(res)
        if isinstance(res, (tuple,list)):
            result = []
            for item_ in res:
                if isinstance(item_, dict):
                    result.append(NboxRecord(item_))
                else:
                    result.append(item_)
            return result
        return res

    def __str__(self):
        return self._record.get("name",
                                self._record.get("label", self._record.get("display", self._record.get("slug", ""))))

    def __repr__(self):
        return self._record.get("name",
                                self._record.get("label", self._record.get("slug", self._record.get("display")))) \
            or "unknown"

    def __format__(self, fmt):
        return format(self.__str__(), fmt)


class NboxDevice(NboxRecord):
    """
    Netbox Device record
    """
    __slots__ = ("iFaces_tags",  "primary_ip", "interface_count")

    def __init__(self, device: dict):  # pynetbox.core.response.Record):
        super().__init__(device)
        self.device_id = self.id
        self.iFaces_tags = {}
        self.interface_count = device.get('interface_count')
        self.primary_ip = None


class NetboxClient:
    """
    Netbox API client
    """
    def __init__(self, url: str, token: str):
        self.log = logging.getLogger('nsg-netbox')
        self._base_url = f"{url.rstrip('/')}/api"
        self._token = token
        self._http_session = Session()
        self._version = None
        headers = dict(accept="application/json;")
        headers["authorization"] = "Token {}".format(self._token)
        self._http_session.headers.update(headers)

        self._mapping = {}

        self._models = self._r("GET", f"{self._base_url}/")
        for k, url in self._models.items():
            res = self._r("GET", url)
            for ent, url1 in res.items():
                if self._mapping.get(ent):
                    ent = f"{k}.{ent}"
                self._mapping[ent] = url1
        self.devices_count = self.count("devices")

    @property
    def version(self) -> float:
        """
        get netbox minor version
        :return: netbox version
        """

        version = self._version or self._mapping.get('netbox-version')
        if version is None:
            try:
                res = self._http_session.get(url=self._base_url + "/status")
            except Exception as e:
                self.log.error(f"netbox connection error: {e}")
                return None

            if res.status_code == http.HTTPStatus.OK:
                try:
                    resp = res.json()
                    version = resp.get("netbox-version")
                except exceptions.JSONDecodeError:
                    pass
            if not version:
                res = self._http_session.get(url=self._base_url)
                version = res.headers.get("API-Version", "")
                if not version:
                    return None
        try:
            self._version = version
            return float(".".join(version.split("-")[0].split(".")[:2]))
        except ValueError:
            return None

    def get(self, entity: str = "", filters: dict = {}, key: int = None, **kwargs):
        """
        Get result from Netbox API for specified endpoint (entity)
        :param entity: name pf endpoint
        :param filters: request filter
        :param key: entity id
        :param kwargs: request extra parameters
        :return: list of entities
        """
        res = self.request(method="GET", entity=entity, filters=filters, key=key, **kwargs)
        return res.get("results") if not None else None

    def request(self, method: str = "GET", entity: str = "", filters: dict = {}, key: int = None, **kwargs):
        url = self._mapping.get(entity.replace("_", "-"))
        if not url:
            raise ValueError(f"Wrong Netbox endpoint <{entity}>")
        if key:
            url = f"{url}{key}"
        return self._r(method, url, params=filters, **kwargs)

    def _r(self, method, url, params=None, headers=None, data=None, json=None, **kwargs):
        """Makes a request.

        Makes a request to NetBox's API

        :Returns: List of `Response` objects returned from the
            endpoint.
        """

        res: requests.Response = self._http_session.request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            data=data,
            json=json,
            **kwargs
        )
        if res.status_code == 200:
            try:
                return res.json()
            except JSONDecodeError as e:
                self.log.error(f"NetboxClient: Get json decode error: {e}")
                return None
        self.log.error(f"NetboxClient: Netbox request {res.request.url} returns {res.status_code}")
        return None

    def count(self, entity: str, filters: dict = {}) -> int:
        """
        get model entities count
        :return: number of entities in netbox db
        """

        filters.update({"limit": 0})
        res = self.request(method="GET", entity=entity, filters=filters)
        if res and isinstance(res, dict):
            return res["count"]
        return None
