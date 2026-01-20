# HomematicIP Prometheus Exporter

Code forked from
[auhlig/homematicip-exporter](https://github.com/auhlig/homematicip-exporter)
as an -exercise in vibe coding.. This fork introduces significant architectural
changes, modernizes the stack, and refines the metrics exposed.

### Key Differences from Upstream

**Architecture & Core**
*   **Real-time Updates**: Implemented a WebSocket listener to receive events instantly, bypassing REST API rate limits and removing the need for frequent polling.
*   **Modern Stack**: Updated to Python 3.14 and the latest `homematicip` library.
*   **On-demand Collection**: Refactored the collector to receive data from Websocket with periodic synchronization from the HmIP REST API.
*   **Cleanup**: Removed code for devices I don't have

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
