import argparse
import sys
import logging
import homematicip
import prometheus_client
import asyncio
from prometheus_client import Counter
from prometheus_client.core import GaugeMetricFamily
from homematicip.async_home import AsyncHome
from homematicip.device import WallMountedThermostatPro, FloorTerminalBlock12
from homematicip.base.functionalChannels import FloorTerminalBlockMechanicChannel

logging.basicConfig(
    level=logging.INFO, format="%(asctime)-15s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)


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
        self.__rest_sync_interval = int(args.rest_sync_interval)
        self.__config = None

        logging.info(
            "using config file '{}' and exposing metrics on port '{}'".format(
                args.config_file, self.__metric_port
            )
        )

        self.__load_config(args.config_file, args.auth_token, args.access_point)
        self.__home_client = AsyncHome()
        self.__event_counter = Counter(
            "hmip_websocket_events_count_total",
            "Number of events received from HomematicIP WebSocket",
            ["event_type", "id", "label", "type"],
        )
        self.__event_byte_counter = Counter(
            "hmip_websocket_events_bytes_total",
            "Total bytes received from HomematicIP WebSocket",
        )

    def __load_config(self, config_file, auth_token, access_point):
        if auth_token and access_point:
            self.__config = homematicip.HmipConfig(
                auth_token=auth_token,
                access_point=access_point,
                log_level=self.__log_level,
                log_file="hmip.log",
                raw_config=None,
            )
        else:
            self.__config = homematicip.load_config_file(config_file=config_file)

    async def __process_raw_message(self, message):
        self.__event_byte_counter.inc(len(str(message)))

    async def start(self):
        try:
            await self.__home_client.init_async(
                self.__config.access_point, self.__config.auth_token
            )
            await self.__home_client.get_current_state_async()
            self.__home_client.onEvent += self.__process_event
            await self.__home_client.enable_events(additional_message_handler=self.__process_raw_message)
            await self.__periodic_collection()
        except Exception as e:
            logging.fatal(
                "Initializing HomematicIP client failed with: {}".format(str(e))
            )
            sys.exit(1)

    def __process_event(self, event_list):
        for event in event_list:
            logging.info("EventType: {} Data: {}".format(event["eventType"], event["data"]))

            try:
                event_type = event["eventType"]
                event_data = event["data"]

                # Extract device info if available
                device_id = ""
                device_label = ""
                type_ = ""

                if isinstance(event_data, dict):
                    if "device" in event_data:
                         device_id = event_data["device"].get("id", "")
                         device_label = event_data["device"].get("label", "")
                    elif "group" in event_data:
                         device_id = event_data["group"].get("id", "")
                         device_label = event_data["group"].get("label", "")
                    elif "id" in event_data:
                         device_id = event_data["id"]
                         if self.__home_client:
                             device = self.__home_client.search_device_by_id(device_id)
                             if device:
                                 device_label = device.label

                    type_ = event_data.get("type", "")

                self.__event_counter.labels(
                    event_type=event_type,
                    id=device_id,
                    label=device_label,
                    type=type_
                ).inc()

            except Exception as e:
                logging.error("Error logging event: %s", e)

    async def __periodic_collection(self):
        while True:
            try:
                await asyncio.sleep(self.__rest_sync_interval)
                await self.__home_client.get_current_state_async()
            except Exception as e:
                logging.warning("Periodic collection failed: %s", e)

    def collect(self):
        """
        collect discovers all devices and generates metrics
        """
        labelnames = ["room", "device_label"]
        detail_labelnames = [
            "device_type",
            "firmware_version",
            "permanently_reachable",
            "device_id",
            "model_type",
            "connection_type",
        ]

        # Home Metrics
        version_info = GaugeMetricFamily(
            "hmip_version_info", "HomematicIP info", labels=["api_version"]
        )

        metric_duty_cycle_ratio = GaugeMetricFamily(
            "hmip_duty_cycle",
            "The current duty cycle of the access point",
        )

        metric_weather_temperature = GaugeMetricFamily(
            "hmip_weather_temperature", "Weather Temperature", labels=["location"]
        )
        metric_weather_humidity = GaugeMetricFamily(
            "hmip_weather_humidity", "Weather Humidity", labels=["location"]
        )
        metric_weather_vapor_amount = GaugeMetricFamily(
            "hmip_weather_vapor_amount", "Weather Vapor Amount", labels=["location"]
        )
        metric_wind_speed = GaugeMetricFamily(
            "hmip_weather_wind_speed", "Wind Speed", labels=["location"]
        )
        metric_min_temperature = GaugeMetricFamily(
            "hmip_weather_min_temperature", "Minimum Temperature", labels=["location"]
        )
        metric_max_temperature = GaugeMetricFamily(
            "hmip_weather_max_temperature", "Maximum Temperature", labels=["location"]
        )

        # Device Metrics
        metric_temperature_actual = GaugeMetricFamily(
            "hmip_current_temperature_celsius", "Actual temperature", labels=labelnames
        )
        metric_temperature_setpoint = GaugeMetricFamily(
            "hmip_set_temperature_celsius", "Set point temperature", labels=labelnames
        )
        metric_valve_adaption_needed = GaugeMetricFamily(
            "hmip_valve_adaption_needed", "must the adaption re-run?", labels=labelnames
        )
        metric_temperature_offset = GaugeMetricFamily(
            "hmip_temperature_offset",
            "the offset temperature for the thermostat",
            labels=labelnames,
        )
        metric_heating_valve_position = GaugeMetricFamily(
            "hmip_heating_valve_position",
            "the current position of the valve 0.0 = closed, 1.0 max opened",
            labels=labelnames + ["channel", "channel_name"],
        )
        metric_humidity_actual = GaugeMetricFamily(
            "hmip_current_humidity_relative", "Actual Humidity", labels=labelnames
        )
        metric_vapor_amount = GaugeMetricFamily(
            "hmip_vapor_amount", "Vapor Amount", labels=labelnames
        )
        metric_low_bat = GaugeMetricFamily(
            "hmip_low_bat", "Low Battery", labels=labelnames
        )
        metric_unreach = GaugeMetricFamily(
            "hmip_unreachable", "Unreachable", labels=labelnames
        )
        metric_config_pending = GaugeMetricFamily(
            "hmip_config_pending", "Configuration Pending", labels=labelnames
        )
        metric_duty_cycle = GaugeMetricFamily(
            "hmip_duty_cycle_limited", "Duty Cycle Reached", labels=labelnames
        )
        metric_last_status_update = GaugeMetricFamily(
            "hmip_last_status_update", "Device last status update", labels=labelnames
        )
        metric_device_info = GaugeMetricFamily(
            "hmip_device_info",
            "Device information",
            labels=labelnames + detail_labelnames,
        )

        metric_valve_protection_duration = GaugeMetricFamily(
            "hmip_valve_protection_duration",
            "Valve Protection Duration",
            labels=labelnames,
        )
        metric_valve_protection_switching_interval = GaugeMetricFamily(
            "hmip_valve_protection_switching_interval",
            "Valve Protection Switching Interval",
            labels=labelnames,
        )
        metric_rssi_device_value = GaugeMetricFamily(
            "hmip_rssi_device_value", "RSSI device value", labels=labelnames
        )
        metric_rssi_peer_value = GaugeMetricFamily(
            "hmip_rssi_peer_value", "RSSI peer value", labels=labelnames
        )
        metric_valve_flow_error = GaugeMetricFamily(
            "hmip_valve_flow_error", "Valve Flow Error", labels=labelnames
        )
        metric_valve_water_error = GaugeMetricFamily(
            "hmip_valve_water_error", "Valve Water Error", labels=labelnames
        )

        try:
            # Weather Info
            if self.__home_client.weather:
                w = self.__home_client.weather
                if w.temperature:
                    metric_weather_temperature.add_metric(
                        [self.__home_client.location.city], w.temperature
                    )
                if w.humidity:
                    metric_weather_humidity.add_metric(
                        [self.__home_client.location.city], w.humidity
                    )
                if w.vaporAmount:
                    metric_weather_vapor_amount.add_metric(
                        [self.__home_client.location.city], w.vaporAmount
                    )
                if w.windSpeed:
                    metric_wind_speed.add_metric(
                        [self.__home_client.location.city], w.windSpeed
                    )
                if w.minTemperature:
                    metric_min_temperature.add_metric(
                        [self.__home_client.location.city], w.minTemperature
                    )
                if w.maxTemperature:
                    metric_max_temperature.add_metric(
                        [self.__home_client.location.city], w.maxTemperature
                    )

            # Version Info
            if self.__home_client.currentAPVersion:
                version_info.add_metric([self.__home_client.currentAPVersion], 1)
                yield version_info

            # Duty Cycle Info
            if self.__home_client.dutyCycle:
                metric_duty_cycle_ratio.add_metric([], self.__home_client.dutyCycle)
                yield metric_duty_cycle_ratio

            for g in self.__home_client.groups:
                if g.groupType == "META":
                    for d in g.devices:
                        # Device Info
                        metric_device_info.add_metric(
                            [
                                g.label,
                                d.label,
                                d.deviceType.lower(),
                                d.firmwareVersion,
                                str(d.permanentlyReachable),
                                d.id,
                                d.modelType,
                                str(d.connectionType),
                            ],
                            1,
                        )
                        if d.lastStatusUpdate:
                            metric_last_status_update.add_metric(
                                [g.label, d.label], d.lastStatusUpdate.timestamp()
                            )

                        # RSSI Metrics
                        if getattr(d, "rssiDeviceValue", None):
                            metric_rssi_device_value.add_metric(
                                [g.label, d.label], d.rssiDeviceValue
                            )
                        if getattr(d, "rssiPeerValue", None):
                            metric_rssi_peer_value.add_metric(
                                [g.label, d.label], d.rssiPeerValue
                            )

                        # Status Metrics
                        if getattr(d, "lowBat", None) is not None:
                            metric_low_bat.add_metric([g.label, d.label], int(d.lowBat))
                        if getattr(d, "unreach", None) is not None:
                            metric_unreach.add_metric(
                                [g.label, d.label], int(d.unreach)
                            )
                        if getattr(d, "configPending", None) is not None:
                            metric_config_pending.add_metric(
                                [g.label, d.label], int(d.configPending)
                            )
                        if getattr(d, "dutyCycle", None) is not None:
                            metric_duty_cycle.add_metric(
                                [g.label, d.label], int(d.dutyCycle)
                            )

                        # Specific Metrics
                        if isinstance(d, WallMountedThermostatPro):
                            if d.actualTemperature:
                                metric_temperature_actual.add_metric(
                                    [g.label, d.label], d.actualTemperature
                                )
                            if d.setPointTemperature:
                                metric_temperature_setpoint.add_metric(
                                    [g.label, d.label], d.setPointTemperature
                                )
                            if d.humidity:
                                metric_humidity_actual.add_metric(
                                    [g.label, d.label], d.humidity
                                )
                            if hasattr(d, "vaporAmount") and d.vaporAmount:
                                metric_vapor_amount.add_metric(
                                    [g.label, d.label], d.vaporAmount
                                )
                            if (
                                hasattr(d, "temperatureOffset")
                                and d.temperatureOffset is not None
                            ):
                                metric_temperature_offset.add_metric(
                                    [g.label, d.label], d.temperatureOffset
                                )
                        elif isinstance(d, FloorTerminalBlock12):
                            if (
                                hasattr(d, "valveProtectionDuration")
                                and d.valveProtectionDuration is not None
                            ):
                                metric_valve_protection_duration.add_metric(
                                    [g.label, d.label], d.valveProtectionDuration
                                )
                            if (
                                hasattr(d, "valveProtectionSwitchingInterval")
                                and d.valveProtectionSwitchingInterval is not None
                            ):
                                metric_valve_protection_switching_interval.add_metric(
                                    [g.label, d.label],
                                    d.valveProtectionSwitchingInterval,
                                )
                            if (
                                hasattr(d, "valveFlowError")
                                and d.valveFlowError is not None
                            ):
                                metric_valve_flow_error.add_metric(
                                    [g.label, d.label], int(d.valveFlowError)
                                )
                            if (
                                hasattr(d, "valveWaterError")
                                and d.valveWaterError is not None
                            ):
                                metric_valve_water_error.add_metric(
                                    [g.label, d.label], int(d.valveWaterError)
                                )
                            for channel in d.functionalChannels:
                                if isinstance(
                                    channel, FloorTerminalBlockMechanicChannel
                                ):
                                    if channel.valvePosition is not None:
                                        metric_heating_valve_position.add_metric(
                                            [
                                                g.label,
                                                d.label,
                                                str(channel.index),
                                                channel.label,
                                            ],
                                            channel.valvePosition,
                                        )

            yield metric_temperature_actual
            yield metric_temperature_setpoint
            yield metric_valve_adaption_needed
            yield metric_temperature_offset
            yield metric_heating_valve_position
            yield metric_humidity_actual
            yield metric_vapor_amount
            yield metric_low_bat
            yield metric_unreach
            yield metric_config_pending
            yield metric_duty_cycle
            yield metric_valve_protection_duration
            yield metric_valve_protection_switching_interval
            yield metric_weather_temperature
            yield metric_weather_humidity
            yield metric_weather_vapor_amount
            yield metric_wind_speed
            yield metric_min_temperature
            yield metric_max_temperature
            yield metric_rssi_device_value
            yield metric_rssi_peer_value
            yield metric_last_status_update
            yield metric_valve_flow_error
            yield metric_valve_water_error
            yield metric_device_info

        except Exception as e:
            logging.warning(
                "collecting status from device(s) failed with: {}".format(str(e))
            )


if __name__ == "__main__":
    import os

    parser = argparse.ArgumentParser(
        description="HomematicIP Prometheus Exporter",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--metric-port",
        default=os.environ.get("METRIC_PORT", 8000),
        help="port to expose the metrics on",
    )
    parser.add_argument(
        "--config-file",
        default=os.environ.get("CONFIG_FILE", "/etc/homematicip-rest-api/config.ini"),
        help="path to the configuration file",
    )
    parser.add_argument(
        "--auth-token",
        default=os.environ.get("AUTH_TOKEN", None),
        help="homematic IP auth token",
    )
    parser.add_argument(
        "--access-point",
        default=os.environ.get("ACCESS_POINT", None),
        help="homematic IP access point id",
    )
    parser.add_argument(
        "--log-level", default=os.environ.get("LOG_LEVEL", 30), help="log level"
    )
    parser.add_argument(
        "--rest-sync-interval",
        default=os.environ.get("REST_SYNC_INTERVAL", 600),
        help="interval in seconds to sync state via REST API",
    )

    args = parser.parse_args()

    # Start up the server to expose the metrics.
    try:
        collector = HomematicIPCollector(args)
        prometheus_client.REGISTRY.register(collector)
        prometheus_client.start_http_server(int(args.metric_port))
        logging.info("Prometheus exporter started on port {}".format(args.metric_port))
        asyncio.run(collector.start())
        # The start method will now run indefinitely
        # while True:
        #    time.sleep(1)
    except Exception as e:
        logging.fatal("Failed to start exporter: {}".format(str(e)))
        sys.exit(1)
