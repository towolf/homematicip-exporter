import argparse
import sys
import time
import logging
import homematicip
import prometheus_client
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
from homematicip.home import Home, EventType
from homematicip.device import WallMountedThermostatPro, TemperatureHumiditySensorDisplay, \
    PlugableSwitch

logging.basicConfig(level=logging.INFO, format='%(asctime)-15s %(message)s', datefmt="%Y-%m-%d %H:%M:%S")


class HomematicIPCollector(object):
    """
    Prometheus Exporter for Homematic IP devices
    """
    def __init__(self, args):
        """
        initializes the exporter

        :param args: the argparse.Args
        """
        
        self.__home_client = None
        self.__metric_port = int(args.metric_port)
        self.__log_level = int(args.log_level)

        logging.info(
            "using config file '{}' and exposing metrics on port '{}'".format(args.config_file, self.__metric_port)
        )

        self.__init_client(args.config_file, args.auth_token, args.access_point)

    def __init_client(self, config_file, auth_token, access_point):
        if auth_token and access_point:
            config = homematicip.HmipConfig(
                auth_token=auth_token,
                access_point= access_point,
                log_level=self.__log_level,
                log_file='hmip.log',
                raw_config=None,
            )
        else:
            config = homematicip.load_config_file(config_file=config_file)

        try:
            self.__home_client = Home()
            self.__home_client.set_auth_token(config.auth_token)
            self.__home_client.init(config.access_point)
        except Exception as e:
            logging.fatal(
                "Initializing HomematicIP client failed with: {}".format(str(e))
            )
            sys.exit(1)

    def collect(self):
        """
        collect discovers all devices and generates metrics
        """
        namespace = 'homematicip'
        labelnames = ['room', 'device_label']
        detail_labelnames = ['device_type', 'firmware_version', 'permanently_reachable']

        # Metrics
        version_info = GaugeMetricFamily(
            'homematicip_version_info',
            'HomematicIP info',
            labels=['api_version']
        )
        
        metric_temperature_actual = GaugeMetricFamily(
            'homematicip_temperature_actual',
            'Actual temperature',
            labels=labelnames
        )
        metric_temperature_setpoint = GaugeMetricFamily(
            'homematicip_temperature_setpoint',
            'Set point temperature',
            labels=labelnames
        )
        metric_valve_adaption_needed = GaugeMetricFamily(
            'homematicip_valve_adaption_needed',
            'must the adaption re-run?',
            labels=labelnames
        )
        metric_temperature_offset = GaugeMetricFamily(
            'homematicip_temperature_offset',
            'the offset temperature for the thermostat',
            labels=labelnames
        )
        metric_valve_position = GaugeMetricFamily(
            'homematicip_valve_position',
            'the current position of the valve 0.0 = closed, 1.0 max opened',
            labels=labelnames
        )
        metric_humidity_actual = GaugeMetricFamily(
            'homematicip_humidity_actual',
            'Actual Humidity',
            labels=labelnames
        )
        metric_last_status_update = GaugeMetricFamily(
            'homematicip_last_status_update',
            "Device last status update",
            labels=labelnames
        )
        metric_device_info = GaugeMetricFamily(
            'homematicip_device_info',
            'Device information',
            labels=labelnames+detail_labelnames
        )

        try:
            self.__home_client.get_current_state()
            
            # Version Info
            if self.__home_client.currentAPVersion:
                 version_info.add_metric([self.__home_client.currentAPVersion], 1)
                 yield version_info

            for g in self.__home_client.groups:
                if g.groupType == "META":
                    for d in g.devices:
                        # Device Info
                        metric_device_info.add_metric(
                            [g.label, d.label, d.deviceType.lower(), d.firmwareVersion, str(d.permanentlyReachable)], 1
                        )
                        if d.lastStatusUpdate:
                             metric_last_status_update.add_metric([g.label, d.label], d.lastStatusUpdate.timestamp())

                        # Specific Metrics
                        if isinstance(d, (WallMountedThermostatPro, TemperatureHumiditySensorDisplay)):
                            if d.actualTemperature:
                                metric_temperature_actual.add_metric([g.label, d.label], d.actualTemperature)
                            if d.setPointTemperature:
                                metric_temperature_setpoint.add_metric([g.label, d.label], d.setPointTemperature)
                            if d.humidity:
                                metric_humidity_actual.add_metric([g.label, d.label], d.humidity)
            
            yield metric_temperature_actual
            yield metric_temperature_setpoint
            yield metric_valve_adaption_needed
            yield metric_temperature_offset
            yield metric_valve_position
            yield metric_humidity_actual
            yield metric_last_status_update
            yield metric_device_info

        except Exception as e:
            logging.warning(
                "collecting status from device(s) failed with: {}".format(str(e))
            )

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='HomematicIP Prometheus Exporter',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--metric-port',
                        default=8000,
                        help='port to expose the metrics on')
    parser.add_argument('--config-file',
                        default='/etc/homematicip-rest-api/config.ini',
                        help='path to the configuration file')
    parser.add_argument('--auth-token',
                        default=None,
                        help='homematic IP auth token')
    parser.add_argument('--access-point',
                        default=None,
                        help='homematic IP access point id')
    parser.add_argument('--log-level',
                        default=30,
                        help='log level')

    args = parser.parse_args()
    
    # Start up the server to expose the metrics.
    try:
        collector = HomematicIPCollector(args)
        prometheus_client.REGISTRY.register(collector)
        prometheus_client.start_http_server(int(args.metric_port))
        logging.info("Prometheus exporter started on port {}".format(args.metric_port))
        while True:
            time.sleep(1)
    except Exception as e:
        logging.fatal("Failed to start exporter: {}".format(str(e)))
        sys.exit(1)
