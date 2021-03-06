
FROM python:3

WORKDIR /usr/src/netspyglass-netbox
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY nsg-netbox.py ./
COPY nsgapi.py ./

CMD [ "python", "./nsg-netbox.py"]
