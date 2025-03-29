#!/bin/bash
cd /home/pi/fyp/webapp
gunicorn -w 2 -b 0.0.0.0:5000 app:app & > /home/pi/fyp/gunicorn.log
sleep 2
cd ~
ngrok http 5000 > /home/pi/fyp/ngrok.log 2>&1 &


