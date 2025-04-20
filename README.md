# Victron VE.Direct MQTT Charger Controller

A Python program to read voltage/current from a Victron Blue Smart charger via VE.Direct, publish to Home Assistant via MQTT (with discovery & availability), and accept charge-current limit updates via MQTT to send back to the charger.

## Installation Software

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
cd /opt
sudo git clone https://github.com/bdynamic/Victron_BlueSmart_IP22_Homeassistant.git
cd Victron_BlueSmart_IP22_Homeassistant

pip install -r requirements.txt
```

### Config & running as a Service
#### Create the config file
Create the config file e.g. in /etc/itbat-charger.yaml
Adjust:
  - Serial port
  - MQTT Username
  - MQTT Password 
  - MQTT Topic if applicable

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

#### Systemd Service
Create /etc/systemd/system/itbat-charger.service:
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

### Configuration of Homeassistant

#### Creating the Current slider
Create a slider for setting the Current by adding this to configuration.yaml:
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

#### MQTT Publish Automation
Add to your automations.yaml:
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


## Interfacing the Charger
### How to open the Charger
    
First remove the 4 marked screws on the bottom side of the charger.    
![Bottom](/Images/charger_bottom.png)   
   
Now you can slide the top cover 1 centimeter down and remove it.    
![Front](/Images/charger_front.png)   
   
You can see on the bottom right side the 6pin connector we need to connect.   
     
You can use a short (about 10cm) 6pin to 6pin flat ribbon cable with the 6pin sockets to connect the charger to the adapter.   
The cable can be routed outside at the right side of the battery terminals (marked with red line).   
![Cable](/Images/charger_bottom_cable.png)    
    
    
### Connect USB to TTL Converter
     
![Victron FTDI Schematic](/Images/Victron_BlueSmart_ftdi.jpg)
      
On the picture the jumper for the TTL level is wrong. 
IMPORTANT: change the jumper to 3.3V    

You have to use TTL to USB adapter for 3.3V TTL level.   
If you use an isolated adapter you have to connect the 3.3V pin to the adapter.
If you do not have an isolated Adapter DONT CONNECT to the 3.3V Pin! 




