#!/bin/bash
cd /home/pi/fyp/webapp
/home/pi/.local/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app &
sleep 5
/usr/local/bin/ngrok http :5000 --log=stdout > /home/pi/fyp/ngrok.log 2>&1 &
sleep 10
curl --silent http://localhost:4040/api/tunnels | grep -o 'https://[^"]*' | head -n 1 > /home/pi/fyp/ngrok_url.txt


