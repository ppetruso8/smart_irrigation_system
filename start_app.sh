#!/bin/bash
cd /home/pi/fyp/webapp
/home/pi/.local/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app &
sleep 5
/usr/local/bin/ngrok http :5000 --log=stdout > /home/pi/fyp/ngrok.log 2>&1 &
sleep 10
grep -o "url=https://[^ ]*" /home/pi/fyp/ngrok.log | head -n 1 | cut -d= -f2 > /home/pi/fyp/ngrok_url.txt


