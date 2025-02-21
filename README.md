# Detailed Geth Synchronization Stages Monitor
**Under development / testing**

This project, based on [basic-eth2-node-monitor](https://github.com/Web3-Pi/basic-eth2-node-monitor), allows users to track the state of Geth synchronization and visualize it using Grafana.

## Requirements
- Python > 3.9
- InfluxDB database for storing data  
- Grafana server to represent stored data visually  
- A working Ethereum node with the Geth consensus client  

## Installation
### Download the repository
```sh
sudo apt-get -y install git
git clone https://github.com/Web3-Pi/geth-sync-stages-monitoring.git
```
### Run as a service (recommended)
```sh
geth-sync-stages-monitoring
chmod +x *.sh
sudo ./create_service.sh
```
### Alternatively, run once
```sh
cd geth-sync-stages-monitoring
chmod +x *.sh
sudo ./run.sh
```
To stop the program, press Ctrl + C.
## Settings
Default settings are the same as in basic-eth2-node-monitor.
If further customization is needed, you can modify the conf.py file.

Most variables in that file are self-explanatory, but a few will be explicitly explained:

* MAX_QUEUE_LEN – Determines how many recent logs are analyzed.
* SYNC_STAGES – A dictionary that stores phrases from logs indicating different stages of Geth synchronization.

To track fewer stages, you can comment out certain lines. If you want to add a new stage to track, you need to add a new entry to the dictionary in the following format:
```
"Phrase indicating the stage is running": [False, "name_of_stage"]
```
If there is more than one phrase that indicates a stage, you can add additional phrases to the list after "name_of_stage", similar to how it is done for "generating_state_snapshot". If you want to visualize a new stage, you will also need to modify the Grafana dashboard.

## How It Works
This app works by reading Geth logs and analyzing them to determine which stage is currently running. It periodically sends the state of synchronization stages to InfluxDB, allowing them to be visualized using a Gantt-like chart. Additionally, it sends information about the start of each stage, which can be displayed on various charts using Grafana annotations.
