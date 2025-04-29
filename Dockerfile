
FROM python:3.9

WORKDIR /usr/src/netspyglass-netbox
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p config
RUN mkdir -p src
RUN mkdir -p test_data
COPY src/ ./src/
COPY config/ ./config/
COPY test_data/ ./test_data/
COPY nsg_netbox.py ./
COPY tests.py ./

CMD [ "python", "nsg_netbox.py"]
