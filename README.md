# Henhouse

### Clone git repository
`git clone git@github.com:DominikFarlik/henhouse.git`
### Move into project directory
`cd henhouse`
### Create and activate virtual env
#### Create:
`python3 -m venv venv`
#### Activate:
`source venv/bin/activate`
### Install requirements
`pip install -r requirements.txt`
### Create configuration file
`nano data/config.ini`
#### Example configuration:
```
[API]
username = <Terminal username for api>
password = <Terminal password for api>
timezone_offset = 120
url = https://itaserver-staging.mobatime.cloud
resend_timer = 1800
fail_limit = 10

[Constants]
lay_counter = 35
lay_time = 60
leave_time = 10

[DB]
file_path = ./data/henhouse.db

[Readers]
/dev/ttyUSB0 = 0
/dev/ttyUSB1 = 1
/dev/ttyUSB2 = 2
/dev/ttyUSB3 = 3
/dev/ttyUSB4 = 4
/dev/ttyUSB5 = 5
/dev/ttyUSB6 = 6
/dev/ttyUSB7 = 7
/dev/ttyUSB8 = 8
/dev/ttyUSB9 = 9
```
|      **Value**      | Description                                                                                                                                    |
|:-------------------:|------------------------------------------------------------------------------------------------------------------------------------------------|
| **timezone_offset** | Difference between UTC and Local time of the terminal in minutes. E.g local time in CEST is 120.                                               |
|       **url**       | Url of api server.                                                                                                                             |
|  **resend_timer**   | Delay(in seconds) between resending failed requests to api.                                                                                    |
|   **fail_limit**    | Number of attempts to resend failed request until it is sent to error endpoint.                                                                |
|   **lay_counter**   | Number of chip reads to determine whether egg was laid. Recommend number slightly over half of lay time. (Chip is read ± 1.5 times per second) |
|    **lay_time**     | Duration of time(in seconds) to determine whether egg was laid.                                                                                |
|   **leave_time**    | Duration of time(in seconds) to determine whether chicken has left the reader.                                                                 |
|    **file_path**    | Path to database file <./path/from/root/dir.db>. Default:                                                                                      |
|    **[Readers]**    | Mapping reader ports and names                                                                                                                 |
#### Save and exit: `^S ^X`
### [OPTIONAL] Get api credentials, if you don't have them already
`python3 -m app activate`
#### There you will enter the HWID and activation code and get login credentials for api
#### rows: `Username` and `Password`

### Run program
`python3 -m app run`

## Linux service for app
### Allow user services:
`loginctl enable-linger pi`
### Create directory:
`mkdir -p /home/pi/.config/systemd/user`
### Create file:
`nano /home/pi/.config/systemd/user/henhouse.service`
### and paste:
```
[Unit]
Description=Henhouse Python Service
After=network.target

[Service]
Type=simple
ExecStart=/home/pi/henhouse/venv/bin/python -m app
WorkingDirectory=/home/pi/henhouse
Environment="PYTHONPATH=/home/pi/henhouse"
Restart=on-failure
StandardOutput=append:/home/pi/henhouse/henhouse.log
StandardError=append:/home/pi/henhouse/henhouse.log

[Install]
WantedBy=default.target
```
### Load new service:
`systemctl --user daemon-reload`
### Start service:
`systemctl --user start henhouse`
### Enable to start service after system boot:
`systemctl --user enable henhouse`
### If u want to stop service:
`systemctl --user stop henhouse`
### Or restart:
`systemctl --user restart henhouse`

## Using CLI
### Can be used to run the app, get number of unsent records to api, ...
#### Use: `python3 -m app --help`


