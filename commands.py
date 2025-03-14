import base64
import traceback

import commands_configuration
import conv
import datatypes
from uart import UART
from conv import *
import RPi.GPIO as GPIO
from XboxController import XboxController

# ZERO_TURN_SWITCH_PIN = 21
# zero_turn_switch_before = GPIO.input(ZERO_TURN_SWITCH_PIN)

class Commands:
    LOCAL_ID = "LOCAL_ID"

    stats = {"success": 0, "fail_timeout": 0, "fail_crc": 0, "failed_other": 0}

    def __init__(self):
        self.ZERO_TURN_SWITCH_PIN = 21
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.ZERO_TURN_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.zero_turn_switch_before = GPIO.input(self.ZERO_TURN_SWITCH_PIN)
        self.joy = XboxController()

    # noinspection PyTypeChecker
    def perform_command(self, uart: UART, command: str, controller_id: int = -1, args: dict = None) -> dict:
        try:
            result: dict = None

            if command == "LOCAL_ID":
                result = {"id": self.get_local_controller_id(uart)}

            if command == "COMM_GET_VALUES":

                # zero turn switch
                zero_turn_switch_after = GPIO.input(self.ZERO_TURN_SWITCH_PIN)
                if zero_turn_switch_after is not self.zero_turn_switch_before:
                    if zero_turn_switch_after == GPIO.HIGH:
                        self.COMM_SET_ZERO_TURN(uart, {"zero_turn": 0}, controller_id)
                    else:
                        self.COMM_SET_ZERO_TURN(uart, {"zero_turn": 1}, controller_id)
                    self.zero_turn_switch_before = zero_turn_switch_after

                # Joystick RC
                [throttle, board] = self.joy.read()
                self.COMM_SET_REMOTE_CONTROL(uart, {"throttle": throttle, "board": board}, controller_id)

                result = self.COMM_GET_VALUES(uart, controller_id)

            if command == "COMM_GET_VALUES_SETUP":
                result = self.COMM_GET_VALUES_SETUP(uart, controller_id)

            if command == "COMM_GET_VALUES_PIDISPLAY":
                result = self.COMM_GET_VALUES_PIDISPLAY(uart, controller_id)

            # if command == "COMM_SET_ZERO_TURN":
            #     result = self.COMM_SET_ZERO_TURN(uart, controller_id)
        
            if command == "COMM_FW_VERSION":
                result = self.COMM_FW_VERSION(uart, controller_id)

            if command == "COMM_REBOOT":
                self.COMM_REBOOT(uart, controller_id)
                result = dict()

            if command == "COMM_PING_CAN":
                result = self.COMM_PING_CAN(uart, controller_id)

            if command == "COMM_SET_CURRENT_BRAKE":
                self.COMM_SET_CURRENT_BRAKE(uart, args, controller_id)         # data: {"current": "0"}
                result = dict()

            if command == "COMM_GET_MCCONF":
                result = self.COMM_GET_MCCONF(uart, controller_id, args)       # data: {"need_bin": False}

            self.stats["success"] += 1
            return result
        except Exception as e:
            if   "Timeout receive packet" in str(e):
                self.stats["fail_timeout"] += 1
            elif "incorrect CRC" in str(e):
                self.stats["fail_crc"] += 1
            else:
                self.stats["failed_other"] += 1

            print("Exception in perform_command")
            print(traceback.format_exc())
            print()
            return None
        
    def COMM_SET_REMOTE_CONTROL(self, uart: UART, args: dict, controller_id: int = -1) -> None:
        throttle = args["throttle"]
        board = args["board"]
        reverse_button = 0  # default: forward(0). Otherwise: backward(1)
        steer_direction = 0  # default: left(0). Otherwise: right(1)
        if throttle < 0:
            reverse_button = 1
        if board < 0:
            steer_direction = 1
        throttle = abs(throttle)
        board = abs(board)
        
        reverse_button_byte = uint8_to_bytes(reverse_button)
        steer_direction_byte = uint8_to_bytes(steer_direction)
        throttle_byte = float32_to_bytes(throttle, 1e2)
        board_byte = float32_to_bytes(board, 1e2)
        data = reverse_button_byte + steer_direction_byte + throttle_byte + board_byte
        print(data)

        # uart.send_command(datatypes.COMM_Types.COMM_SET_ZERO_TURN, controller_id=controller_id, data=data)

        return None
        
    def COMM_GET_VALUES(self, uart: UART, controller_id: int = -1) -> dict:
        uart.send_command(datatypes.COMM_Types.COMM_GET_VALUES, controller_id=controller_id)
        result = uart.receive_packet()

        dec = dict() ; i = 0
        dec["temp_fet_filtered"] = float_from_bytes(result.data[i : i+2])           ; i+=2
        dec["temp_motor_filtered"] = float_from_bytes(result.data[i : i+2])         ; i+=2

        dec["avg_motor_current"] = float_from_bytes(result.data[i : i+4], 1e2, True); i+=4
        dec["avg_input_current"] = float_from_bytes(result.data[i : i+4], 1e2, True); i+=4
        dec["avg_id"] = float_from_bytes(result.data[i : i+4], 1e2)                 ; i+=4
        dec["avg_iq"] = float_from_bytes(result.data[i : i+4], 1e2, True)           ; i+=4

        dec["duty_cycle"] = float_from_bytes(result.data[i : i+2], 1e3)         ; i+=2
        dec["rpm"] = float_from_bytes(result.data[i : i+4], 1e0, True)          ; i+=4
        dec["voltage"] = float_from_bytes(result.data[i : i+2], 1e1)            ; i+=2

        dec["amp_hours"] = float_from_bytes(result.data[i : i+4], 1e4)          ; i+=4
        dec["amp_hours_charged"] = float_from_bytes(result.data[i : i+4], 1e4)  ; i+=4

        dec["watt_hours"] = float_from_bytes(result.data[i : i+4], 1e4)         ; i+=4
        dec["watt_hours_charged"] = float_from_bytes(result.data[i : i+4], 1e4) ; i+=4

        dec["tachometer"] = uint_from_bytes(result.data[i : i+4], True)         ; i+=4
        dec["tachometer_abs"] = uint_from_bytes(result.data[i : i+4])           ; i+=4

        dec["fault_code"] = result.data[i]                                      ; i+=1
        dec["fault_code_desc"] = datatypes.FAULT_Codes(dec["fault_code"]).name

        dec["pid_pos"] = float_from_bytes(result.data[i : i+4], 1e6)            ; i+=4

        dec["controller_id"] = result.data[i]                                   ; i+=1

        dec["temp_mos1"] = float_from_bytes(result.data[i : i+2], 1e1)          ; i+=2
        dec["temp_mos2"] = float_from_bytes(result.data[i : i+2], 1e1)          ; i+=2
        dec["temp_mos3"] = float_from_bytes(result.data[i : i+2], 1e1)          ; i+=2

        dec["avg_vd"] = float_from_bytes(result.data[i : i+4], 1e3)             ; i+=4
        dec["avg_vq"] = float_from_bytes(result.data[i : i+4], 1e3, True)       ; i+=4

        return dec

    def COMM_GET_VALUES_SETUP(self, uart: UART, controller_id: int = -1) -> dict:
        uart.send_command(datatypes.COMM_Types.COMM_GET_VALUES_SETUP, controller_id=controller_id)
        result = uart.receive_packet()

        dec = dict() ; i = 0
        dec["temp_fet_filtered"] = float_from_bytes(result.data[i : i+2])           ; i+=2
        dec["temp_motor_filtered"] = float_from_bytes(result.data[i : i+2])         ; i+=2

        dec["avg_motor_current"] = float_from_bytes(result.data[i : i+4], 1e2, True); i+=4
        dec["avg_input_current"] = float_from_bytes(result.data[i : i+4], 1e2, True); i+=4

        dec["duty_cycle"] = float_from_bytes(result.data[i : i+2], 1e3)         ; i+=2
        dec["rpm"] = float_from_bytes(result.data[i : i+4], 1e0, True)          ; i+=4
        dec["speed"] = float_from_bytes(result.data[i : i+4], 1e3)              ; i+=4

        dec["voltage"] = float_from_bytes(result.data[i : i+2], 1e1)            ; i+=2
        dec["batter_level"] = float_from_bytes(result.data[i : i+2], 1e3)       ; i+=2

        dec["amp_hours"] = float_from_bytes(result.data[i : i+4], 1e4)          ; i+=4
        dec["amp_hours_charged"] = float_from_bytes(result.data[i : i+4], 1e4)  ; i+=4

        dec["watt_hours"] = float_from_bytes(result.data[i : i+4], 1e4)         ; i+=4
        dec["watt_hours_charged"] = float_from_bytes(result.data[i : i+4], 1e4) ; i+=4

        dec["tachometer"] = uint_from_bytes(result.data[i : i+4], True)         ; i+=4
        dec["tachometer_abs"] = uint_from_bytes(result.data[i : i+4])           ; i+=4

        dec["pid_pos"] = float_from_bytes(result.data[i : i+4], 1e6)            ; i+=4

        dec["fault_code"] = result.data[i]                                      ; i+=1
        dec["fault_code_desc"] = datatypes.FAULT_Codes(dec["fault_code"]).name

        dec["controller_id"] = result.data[i]                                   ; i+=1
        dec["num_vescs"] = result.data[i]                                       ; i+=1

        dec["wh_batt_left"] = float_from_bytes(result.data[i : i+4], 1e3)       ; i+=4
        dec["odometer"] = float_from_bytes(result.data[i : i+4], 1e3)           ; i+=4

        return dec
    
    def COMM_GET_VALUES_PIDISPLAY(self, uart: UART, controller_id: int = -1) -> dict:
        uart.send_command(datatypes.COMM_Types.COMM_GET_VALUES_PIDISPLAY, controller_id=controller_id)
        result = uart.receive_packet()

        dec = dict() ; i = 0
        dec["temp_fet_filtered"] = float_from_bytes(result.data[i : i+2])           ; i+=2
        dec["temp_motor_filtered"] = float_from_bytes(result.data[i : i+2])         ; i+=2

        dec["avg_motor_current"] = float_from_bytes(result.data[i : i+4], 1e2, True); i+=4
        dec["avg_input_current"] = float_from_bytes(result.data[i : i+4], 1e2, True); i+=4
        dec["avg_id"] = float_from_bytes(result.data[i : i+4], 1e2)                 ; i+=4
        dec["avg_iq"] = float_from_bytes(result.data[i : i+4], 1e2, True)           ; i+=4

        dec["duty_cycle"] = float_from_bytes(result.data[i : i+2], 1e3)         ; i+=2
        dec["rpm"] = float_from_bytes(result.data[i : i+4], 1e0, True)          ; i+=4
        dec["voltage"] = float_from_bytes(result.data[i : i+2], 1e1)            ; i+=2

        dec["amp_hours"] = float_from_bytes(result.data[i : i+4], 1e4)          ; i+=4
        dec["amp_hours_charged"] = float_from_bytes(result.data[i : i+4], 1e4)  ; i+=4

        dec["watt_hours"] = float_from_bytes(result.data[i : i+4], 1e4)         ; i+=4
        dec["watt_hours_charged"] = float_from_bytes(result.data[i : i+4], 1e4) ; i+=4

        dec["tachometer"] = uint_from_bytes(result.data[i : i+4], True)         ; i+=4
        dec["tachometer_abs"] = uint_from_bytes(result.data[i : i+4])           ; i+=4

        dec["fault_code"] = result.data[i]                                      ; i+=1
        dec["fault_code_desc"] = datatypes.FAULT_Codes(dec["fault_code"]).name

        dec["pid_pos"] = float_from_bytes(result.data[i : i+4], 1e6)            ; i+=4

        dec["controller_id"] = result.data[i]                                   ; i+=1

        dec["temp_mos1"] = float_from_bytes(result.data[i : i+2], 1e1)          ; i+=2
        dec["temp_mos2"] = float_from_bytes(result.data[i : i+2], 1e1)          ; i+=2
        dec["temp_mos3"] = float_from_bytes(result.data[i : i+2], 1e1)          ; i+=2

        dec["avg_vd"] = float_from_bytes(result.data[i : i+4], 1e3)             ; i+=4
        dec["avg_vq"] = float_from_bytes(result.data[i : i+4], 1e3, True)       ; i+=4

        dec["battery_level"] = float_from_bytes(result.data[i : i+2], 1e3, True); i+=2
        dec["distance"] = float_from_bytes(result.data[i : i+4], 1e3, True)     ; i+=4
        dec["distance_abs"] = float_from_bytes(result.data[i : i+4], 1e3, True) ; i+=4
        dec["odometer"] = float_from_bytes(result.data[i : i+4], 1e3, True)     ; i+=4

        return dec
    
    def COMM_SET_ZERO_TURN(self, uart: UART, args: dict, controller_id: int = -1) -> None:
        zero_turn = args["zero_turn"] # binary true or false
        data = uint8_to_bytes(zero_turn)
        uart.send_command(datatypes.COMM_Types.COMM_SET_ZERO_TURN, controller_id=controller_id, data=data)

        return None

    def COMM_FW_VERSION(self, uart: UART, controller_id: int = -1) -> dict:
        uart.send_command(datatypes.COMM_Types.COMM_FW_VERSION, controller_id=controller_id)
        result = uart.receive_packet()

        dec = dict() ; i = 0
        dec["fw_version"] = result.data[i]          ; i += 1
        dec["fw_version_major"] = result.data[i]    ; i += 1
        dec["fw_version_minor"] = result.data[i]    ; i += 1

        dec["fw_version_generic"] = float(str(dec.get("fw_version")) + "." + str(dec.get("fw_version_major")))

        model = result.data[i-1:]
        model_end = model.find(bytes([0x00]))
        model = model[:model_end]
        dec["hw_name"] = model.decode()
        i += model_end

        uuid = result.data[i:i+12]
        dec["mc_uuid"] = uuid.hex()
        i += 12

        dec["pairing_done"] = result.data[i]        ; i += 1
        dec["test_ver_number"] = result.data[i]     ; i += 1
        dec["hw_type_vesc"] = result.data[i]        ; i += 1
        return dec

    def COMM_SET_CURRENT_BRAKE(self, uart: UART, args: dict, controller_id: int = -1) -> None:
        current = args["current"]

        current = current * 1000
        data = uint32_to_bytes(current)

        uart.send_command(datatypes.COMM_Types.COMM_SET_CURRENT, controller_id=controller_id, data=data)
        return None

    def COMM_GET_APPCONF(self, uart: UART, controller_id: int = -1) -> dict:
        uart.send_command(datatypes.COMM_Types.COMM_GET_APPCONF, controller_id=controller_id)
        result = uart.receive_packet(timeout_ms=500)

        #print(result.data)
        #print(result.data.hex())
        return {"not_parsed_data": base64.b64encode(result.data).decode()}

    def COMM_PING_CAN(self, uart: UART, controller_id: int = -1) -> dict:
        uart.send_command(datatypes.COMM_Types.COMM_PING_CAN, controller_id=controller_id)
        result = uart.receive_packet(timeout_ms=5000)

        vesc_ids = []
        for vesc_id in result.data:
            vesc_ids.append(vesc_id)

        return {'vesc_on_bus': vesc_ids}

    def COMM_GET_MCCONF(self, uart: UART, controller_id: int = -1, args=None) -> dict:
        if args is None: args = {"need_bin": False}
        need_bin = args.get("need_bin", False)

        fw = self.COMM_FW_VERSION(uart, controller_id)

        uart.send_command(datatypes.COMM_Types.COMM_GET_MCCONF, controller_id=controller_id)
        result = uart.receive_packet(timeout_ms=500)

        ok, result = commands_configuration.deserialize_mcconf(result, fw["fw_version_generic"], need_bin)
        return result

    def COMM_REBOOT(self, uart: UART, controller_id: int = -1) -> None:
        uart.send_command(datatypes.COMM_Types.COMM_REBOOT, controller_id=controller_id)
        return None

    def get_local_controller_id(self, uart: UART) -> int:
        mask_controller_id = "00000000 00000010 00000000 00000000"
        com = conv.binstr_to_bytes(mask_controller_id)

        uart.send_command(datatypes.COMM_Types.COMM_GET_VALUES_SELECTIVE, com)
        result = uart.receive_packet()

        return result.data[4]
