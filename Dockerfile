
FROM python:3

WORKDIR /usr/src/netspyglass-netbox
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY net-netbox.py ./
COPY nsgapi.py ./

CMD [ "python", "./net-netbox.py"]
