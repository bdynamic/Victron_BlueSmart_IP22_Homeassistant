# Victron VE.Direct MQTT Charger Controller

A Python program to read voltage and current from a Victron Blue Smart Charger via VE.Direct, publish to Home Assistant via MQTT (with discovery & availability), and accept charge current limit updates via MQTT to send back to the charger.


---

## ⚠️ Disclaimer of Doom ⚠️

This project is **completely unofficial**, has **zero affiliation** with Victron Energy, and was lovingly duct-taped together by enthusiastic nerds for nerds.

By using this, you acknowledge that:

- You are **fully responsible** for what happens to your charger, your MQTT server, your Home Assistant, your eyebrows, and possibly the space-time continuum.
- No warranties, no guarantees, no tech support from Victron, Elon Musk, or your neighbor Klaus.
- If your charger explodes, becomes self-aware, or insists on being called "Blinky the Battery Overlord" — that’s on you.

**Use at your own risk. Hack responsibly. Stay safe.**
---

## 🧙Many Thanks to the Original Wizards

This project stands on the shoulders of giants — or at least one very talented dev:  
👉 [@wasn-eu](https://github.com/wasn-eu) and their glorious repo  
🔗 [github.com/wasn-eu/Victron_BlueSmart_IP22](https://github.com/wasn-eu/Victron_BlueSmart_IP22)

Their code was the Gandalf to our Frodo, the kernel to our driver, the `__init__()` to our `main()`.

We’ve shamelessly borrowed, refactored, extended, and generally tinkered with their original magic to make it play nice with Home Assistant, MQTT, and your inner need for glorious nerd control.

Without their work, this project would still be stuck trying to `import serial` and wondering why `readline()` returns nothing.

**May your baudrates be steady and your chargers forever smart.**
---

## Table of Contents

- [Installation Software](#installation-software)
- [Config & Running as a Service](#config--running-as-a-service)
  - [Create the Config File](#create-the-config-file)
  - [Systemd Service](#systemd-service)
- [Configuration of Home Assistant](#configuration-of-home-assistant)
  - [Creating the Current Slider](#creating-the-current-slider)
  - [MQTT Publish Automation](#mqtt-publish-automation)
- [Interfacing the Charger](#interfacing-the-charger)
  - [How to Open the Charger](#how-to-open-the-charger)
  - [Connect USB to TTL Converter](#connect-usb-to-ttl-converter)

---

## Installation Software

```bash
sudo apt update
sudo apt install -y python3 python3-pip git
cd /opt
sudo git clone https://github.com/bdynamic/Victron_BlueSmart_IP22_Homeassistant.git
cd Victron_BlueSmart_IP22_Homeassistant
pip install -r requirements.txt
```

---

## Config & Running as a Service

### Create the Config File

Create the config file, e.g. at `/etc/itbat-charger.yaml`. Adjust the following:

- Serial port
- MQTT username
- MQTT password
- MQTT topic (if applicable)

```yaml
serial:
  port: /dev/ttyUSB0
  baudrate: 19200

# MQTT connection settings
mqtt:
  host: <IP MQTT BROKER>
  port: 1883
  username: "username"
  password: "password"
  base_topic: "bat_charger"
  current_limit_topic: bat_charger/itbatchrg/curlimit

device:
  name: itbatchrg
  vendor: victron
  initial_current_limit: 10.0

# Logging level: DEBUG, INFO, WARNING, ERROR
log_level: "INFO"
```

### Systemd Service

Create the systemd service file at `/etc/systemd/system/itbat-charger.service`:

```ini
[Unit]
Description=Victron VE.Direct → MQTT Charger Controller
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/victron-mqtt-charger
ExecStart=/opt/victron-mqtt-charger/venv/bin/python charger_controller.py --config /etc/itbat-charger.yaml
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### Enable + start the service

```bash
sudo systemctl daemon-reexec
sudo systemctl enable liontron-mqtt.service
sudo systemctl start liontron-mqtt.service
```

#### Check logs

```bash
journalctl -u liontron-mqtt.service -f
```


---

## Configuration of Home Assistant

### Creating the Current Slider

Add the following to your `configuration.yaml`:

```yaml
input_number:
  itbat_charge_current:
    name: Charge Current Limit
    min: 7.5
    max: 25.0
    step: 0.1
    unit_of_measurement: "A"
    mode: slider
```

### MQTT Publish Automation

Add the following to your `automations.yaml`:

```yaml
- alias: itbat_publish_mqtt_charge_current
  description: "Publishes the charge current limit to MQTT on change"
  mode: single
  initial_state: true
  trigger:
    - platform: state
      entity_id: input_number.itbat_charge_current
  action:
    - service: mqtt.publish
      data:
        topic: "bat_charger/itbatchrg/curlimit"
        payload: "{{ states('input_number.itbat_charge_current') }}"
        qos: 0
        retain: true
```

---

## Interfacing the Charger

### How to Open the Charger

1. Remove the 4 marked screws on the bottom side of the charger.  
   ![Bottom](/Images/charger_bottom.png)  

2. Slide the top cover down about 1 cm and remove it.  
   ![Front](/Images/charger_front.png)  

3. On the bottom-right side, you’ll see the 6-pin connector we need to access.  

Use a short (about 10 cm) 6-pin to 6-pin flat ribbon cable with sockets to connect the charger to the adapter.  
You can route the cable out to the right side of the battery terminals (marked in red).  
![Cable](/Images/charger_bottom_cable.png)

---

### Connect USB to TTL Converter

![Victron FTDI Schematic](/Images/Victron_BlueSmart_ftdi.jpg)

> ⚠️ **Important:** The jumper for the TTL level in the picture is wrong.  
> **Set the jumper to 3.3 V!**

Use a TTL-to-USB adapter that supports **3.3 V TTL level**.

- If you use an **isolated adapter**, connect the 3.3 V pin to the adapter.
- If your adapter is **not isolated**, **do not connect** the 3.3 V pin!

---
