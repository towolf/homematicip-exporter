FROM python:slim
ADD requirements.txt /
RUN pip3 install --upgrade pip
RUN pip3 install -r ./requirements.txt
RUN sed -i 's/HOME_CONTROL_ACCESS_POINT = auto()/HOME_CONTROL_ACCESS_POINT = auto()\n    HOME_CONTROL_ACCESS_POINT_TWO = auto()/' /usr/local/lib/python3.14/site-packages/homematicip/base/enums.py
RUN sed -i 's/DeviceType.HOME_CONTROL_ACCESS_POINT: HomeControlAccessPoint,/DeviceType.HOME_CONTROL_ACCESS_POINT: HomeControlAccessPoint,\n    DeviceType.HOME_CONTROL_ACCESS_POINT_TWO: HomeControlAccessPoint,/' /usr/local/lib/python3.14/site-packages/homematicip/class_maps.py
ADD exporter.py /
ENTRYPOINT [ "python3", "./exporter.py" ]
