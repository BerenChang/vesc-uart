import http.server
import traceback
from typing import Any, Union

import ujson as json
import random
import threading
import urllib.parse
import logic
from network_packet import RequestPacket
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler, HTTPServer
import uart
import serial

logic_obj = logic.Logic()

class ApiServer:
    server: HTTPServer = None

    # self.uart = uart.UART()
    # self.uart.connect("port:///dev/ttyAMA0?speed=115200", 115200)

    class RequestHandler(BaseHTTPRequestHandler):

        def parser(self, method : str) -> RequestPacket:
            result = RequestPacket()

            result.headers = self.headers
            result.method = method

            result.full_url = self.path

            if "Content-Length" in self.headers:
                length = int(self.headers.get('Content-Length'))
                result.body = self.rfile.read(length)

            if "Content-Type" in self.headers and "application/json" in self.headers.get("Content-Type"):
                result.json_root = json.loads(result.body.decode())

            if "?" in result.full_url:
                query = result.full_url[result.full_url.find("?") + 1:]
                data = dict(urllib.parse.parse_qsl(query))
                result.json_root = {**result.json_root, **data}

                result.api_endpoint = result.full_url[:result.full_url.find("?")]
            else:
                result.api_endpoint = result.full_url[result.full_url.find("/"):]

            result.requested_indent = 4

            return result

        def handler(self, method):
            try:
                request = self.parser(method)
            except Exception as e:
                self.send_error(400)
                self.end_headers()

                print("Exception in handler parser(method)")
                print(traceback.format_exc())
                print()
                return

            #i = random.randint(10, 99)
            #print(i, "new request from " + request.client_ip + ":", request.api_endpoint, request.json_root)

            try:
                answer = logic_obj.work_packet(request)
            except Exception as e:
                print(e)
                self.send_error(500)
                self.end_headers()

                print("Exception in logic_obj.work_packet(request)")
                print(traceback.format_exc())
                print()
                return

            if answer is None:
                self.send_error(501)
                self.end_headers()
                return


            #print(i, "answer for " + request.client_ip + ":", answer)

            else:
                self.send_response(200)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()

                answer = json.dumps(answer, indent=request.requested_indent)
                answer = answer.encode(encoding="utf-8")
                try: self.wfile.write(answer)
                except: pass


        def do_GET(self):
            self.handler("get")

        def do_POST(self):
            self.handler("post")

        # noinspection PyShadowingBuiltins
        def log_error(self, format: str, *args: Any) -> None:
            if logic_obj.uart is not None and logic_obj.uart.debug: super().log_error(format, args)
        def log_request(self, code: Union[int, str] = ..., size: Union[int, str] = ...) -> None:
            if logic_obj.uart is not None and logic_obj.uart.debug: super().log_request(code, size)

    def read_serial(*args):
        ser = serial.Serial('/dev/ttyAMA0', 115200, timeout=10)
        while True:
            data = ser.read(16)
            data = [x for x in data]
            print(f"Received: {data[:5]}")

            if data[:5] is not [3,2,11,35,127]:
                ser.read(1)
                print(f"Aligning data: {data}")
            else:
                print(f"Aligned data: {data}")


    def read_uart(*args):
        while True:
            data = self.uart.receive_packet(allow_incorrect_crc=False)
            print(f"Received: {data}")


    def start_server(self, host, port, blocking = True):
        # serial_thread = threading.Thread(target=self.uart.receive_packet(allow_incorrect_crc=False))
        # serial_thread = threading.Thread(target=self.read_uart)
        serial_thread = threading.Thread(target=self.read_serial)
        serial_thread.start()
        if blocking:
            self.__internal_start_server(host, port)
        else:
            threading.Thread(target=self.__internal_start_server, args=(host, port), name="main_server_thread").start()

    def __internal_start_server(self, host, port):
        self.server = HTTPServer((host, port), self.RequestHandler)
        self.server.serve_forever()

    def stop_server(self):
        if self.server is not None:
            self.server.socket.close()
            #self.server.shutdown()
            #self.server.server_close()
