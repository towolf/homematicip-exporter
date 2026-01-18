FROM python:slim
ADD requirements.txt /
RUN pip3 install --upgrade pip
RUN pip3 install -r ./requirements.txt
RUN sed -i 's/HOME_CONTROL_ACCESS_POINT/HOME_CONTROL_ACCESS_POINT_TWO/' /usr/local/lib/python3.14/site-packages/homematicip/base/enums.py /usr/local/lib/python3.14/site-packages/homematicip/class_maps.py
ADD exporter.py /
ENTRYPOINT [ "python3", "./exporter.py" ]
