import base64
import json
import signal
import socket

import serial
import time
from conv import *
import uart
import datatypes
import commands
import network
import sys
import RPi.GPIO as GPIO


print("starting server")
server = network.ApiServer()

ZERO_TURN_SWITCH_PIN = 21

def signal_exit(signum, frame):
    print("stopping service by signal")
    server.stop_server()
    exit(0)

if sys.platform == "linux":
    signal.signal(signal.SIGINT, signal_exit)
    signal.signal(signal.SIGTERM, signal_exit)

server.start_server("0.0.0.0", 2002) # blocking
# exit(0)



##########
## Testing zone
##########

uart = uart.UART(debug=True)
uart.connect("port:///dev/ttyACM0?speed=115200", 115200)
print("started")

GPIO.setmode(GPIO.BCM)
GPIO.setup(ZERO_TURN_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

#time.sleep(15)

while 1:
    sended = int(time.time() * 1000)
    s = commands.Commands()
    #res = s.COMM_FW_VERSION(uart, -1)
    #res = s.COMM_SET_HANDBRAKE(uart, {"current": 1.0}, -1)
    #res2 = s.COMM_SET_HANDBRAKE(uart, {"current": 1.0}, 8)
    #res3 = s.COMM_SET_CURRENT_BRAKE(uart, {"current": 2}, -1)
    #res4 = s.COMM_SET_CURRENT_BRAKE(uart, {"current": 20}, 8)

    #f = s.COMM_GET_MCCONF(uart, -1, {"need_bin": True})
    # f = s.COMM_PING_CAN(uart)
    # f = s.COMM_GET_VALUES(uart)
    # f = s.COMM_GET_VALUES_SETUP(uart)

    switch_state = GPIO.input(ZERO_TURN_SWITCH_PIN)

    # Determine the switch status
    if switch_state == GPIO.LOW:
        f = s.COMM_SET_ZERO_TURN(uart, {"zero_turn": 0}, -1)
    else:
        f = s.COMM_SET_ZERO_TURN(uart, {"zero_turn": 1}, -1)
    
    # f = s.COMM_SET_ZERO_TURN(uart, {"zero_turn": 1}, -1)
    # print(f)
    #b = base64.b64decode(f.get("not_parsed_data"))

    #res = s.COMM_REBOOT(uart, -1)
    #res = json.dumps(res, indent=4)
    #print(b.hex())

    print()
    print()

    #print(json.dumps(f, indent=4))
    #print(len(json.dumps(f, indent=4)))

    #res = s.COMM_FW_VERSION(uart, -1)
    #print(json.dumps(res, indent=4))

    print("req_time:", int((time.time() * 1000) - sended))

    time.sleep(0.8)
    break