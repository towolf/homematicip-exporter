FROM python:3.11-slim-bookworm
ADD exporter.py requirements.txt /
RUN pip3 install --upgrade pip
RUN pip3 install -r ./requirements.txt
ENTRYPOINT [ "python3", "./exporter.py" ]
