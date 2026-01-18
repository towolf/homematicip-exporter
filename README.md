# HomematicIP Prometheus Exporter

Code forked from https://github.com/auhlig/homematicip-exporter as an
exercise in vibe coding.

I stripped some code for devices I don't have, updated to the latest
HmIP library and added some stuff.

The image is ghcr.io/towolf/homematicip-exporter

## Project Overview

This is a Python-based Prometheus Exporter for the HomematicIP Cloud
service. It uses the homematicip library to fetch device and system
states and exposes them as Prometheus metrics  
on a specified port (default 8000).

Key Components

- exporter.py: The core application.
  - Initialization: Connects to the HomematicIP cloud using an auth
    token and access point ID (via arguments or config file).
  - Metrics: Collects a wide range of data including:
    - System: API version, Duty Cycle.
    - Devices: Status (low battery, unreachable), RSSI values, valve
      positions, temperatures (actual/setpoint).
    - Weather: Temperature, humidity, wind speed, vapor amount.
- requirements.txt: Dependencies are `homematicip >= 2.5.0` and
  `prometheus_client >= 0.24.1`.
- Dockerfile: Defines the container image build.
