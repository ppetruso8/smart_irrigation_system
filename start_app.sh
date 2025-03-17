#!/bin/bash
cd /home/pi/fyp/webapp
gunicorn -w 2 -b 0.0.0.0:5000 app:app &
sleep 2
ngrok http 5000 > /home/pi/fyp/ngrok.log 2>&1 &


