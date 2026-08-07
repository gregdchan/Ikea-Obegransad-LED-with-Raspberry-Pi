# Control IKEA Obegränsad using a Raspberry Pi
The IKEA x Swedish House Mafia Obegransad collection included a playful, albeit limited interactive led panel. Thinkerers have since modified it through numerous iterations using a variety of micro-controllers. 

This project offers an alternative to programming in Arduino, instead utilizing a raspberry pi and Python to control the LED. It follows generally the same physical modifications. While I personally used a Raspberry Pi 3, you can can opt for a RP Zero as well.

## Some Things to Note
1. This project is ongoing, continuously debugged and refractored, check back regularly for updates and new features.
2. This project requires you to permanently modify the panel, unsoldering the data chip and soldering new wires. Be careful not to damage the board!
3. The Raspberry Pi requires an active network connection to access controls.

## Features
1. By default, the display shows a clock based on the current location set in the RPi.
2. User can set location and openweathermap api for local temperature
3. Flask is used to create a simple control page accessible by web browser (<devicename>.local:5000)
4. From webpage, you can: turn the display on and off, adjust brightness, add scrolling text, and control scroll speed).

## Coming Soon:
1. Collection of animation loops, controllable from webpage
2. Scrolling Direction
3. Orientation control
4. Addition of APDS 9960 for gesture controls

## Requirements
1. An IKEA Obegransad LED Lamp
2. A Raspberry Pi Zero, 3, or 4 with case
3. A soldering kit, including wires
4. Some double-sided tape or velcro to hold RPi in place
5. A drill and bit to remove the rivets

## Get Started
The first thing you'll want to do is prep the and raspberry pi. 
You can follow [these instructions](https://github.com/ph1p/ikea-led-obegraensad?tab=readme-ov-file#the-panels) on how open, unsolder the old chip, and solder new wires to the pins and button. 

Set up a Raspberry Pi using RP OS with SSH and Wifi configured so its easy to get into once online.
Install Python and [RPi.GPIO](https://pypi.org/project/RPi.GPIO/) on Raspberry Pi.

Next, you'll need to connect the LED pins to the Raspberry pi as mapped below

## GPIO pin mappings
1. P_EN = 17     - Brightness control (PWM pin)
2. P_DI = 2      - Data pin
3. P_CLK = 3     - Clock pin
4. P_CLA = 27    - Latch pin
5. P_KEY = 16    - Key input pin
6. Plus 2 ground pins

Permitting these steps are followed, you should be able to proceed with cloning package in your preferred folder. Once the package is cloned, copy `.env.example` to `.env` and fill in your
[OpenWeatherMap](https://openweathermap.org/api) key and city. `.env` is gitignored, so your key
stays off GitHub. City and key can also be changed at runtime from the web UI.

    cp .env.example .env
    $EDITOR .env
    python3 flask_server.py

## Auto-deploy to the Pi
The Pi runs the server as a systemd unit (`deploy/obegransad.service`) and polls
this repo once a minute via cron (`deploy/autopull.sh`). Push to `main` and the
display picks up the change and restarts itself within 60 seconds.

Setup on the Pi:

    sudo cp deploy/obegransad.service /etc/systemd/system/
    sudo systemctl daemon-reload && sudo systemctl enable --now obegransad
    echo 'gdc ALL=(root) NOPASSWD: /usr/bin/systemctl restart obegransad' | sudo tee /etc/sudoers.d/obegransad
    (crontab -l 2>/dev/null; echo '* * * * * ~/Documents/ikea-obegransad/deploy/autopull.sh >> ~/autopull.log 2>&1') | crontab -

Deploy log: `tail -f ~/autopull.log`. Server status: `systemctl status obegransad`.
