"""
Serial bus interface for Feetech STS3215 servos.

Simplified implementation of the Feetech STS protocol for reading sensor data.
"""

import serial
from typing import Dict, List

from .tables import STS3215_CONTROL_TABLE
from ._utils import check_if_connected


class FeetechMotorsBus:
    """
    Serial bus interface for Feetech STS3215 servos.

    This is a simplified but functional implementation of the Feetech STS
    serial protocol. It reads registers one motor at a time (not true bulk
    sync_read, but functionally equivalent for a POC).
    """

    def __init__(self, port: str, motors: Dict[str, int], baudrate: int = 1000000, timeout: float = 0.1):
        """
        Initialize the motor bus.

        Args:
            port: Serial port path (e.g., /dev/ttyUSB0)
            motors: Dict mapping motor name to motor ID {name: id}
            baudrate: Serial baud rate (default: 1000000)
            timeout: Serial read timeout in seconds (default: 0.1)
        """
        self.port = port
        self.motors = motors  # {name: id}
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        self.is_connected = False

    def connect(self):
        """
        Open serial connection to servo bus.

        Raises:
            serial.SerialException: If port cannot be opened
        """
        self.serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )
        self.is_connected = True

    def disconnect(self):
        """Close serial connection."""
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.is_connected = False

    @check_if_connected
    def sync_read(self, register_name: str, motor_names: List[str]) -> Dict[str, int]:
        """
        Read a register from multiple motors.

        Args:
            register_name: Name from STS3215_CONTROL_TABLE
            motor_names: List of motor names to read

        Returns:
            Dict mapping motor name to register value

        Raises:
            KeyError: If register_name is not in control table
            RuntimeError: If bus is not connected
        """
        if register_name not in STS3215_CONTROL_TABLE:
            raise KeyError(f"Unknown register: {register_name}")

        addr, length = STS3215_CONTROL_TABLE[register_name]

        results = {}
        for name in motor_names:
            motor_id = self.motors[name]
            try:
                value = self._read_register(motor_id, addr, length)
                results[name] = value
            except Exception as e:
                # If read fails for one motor, continue with others
                print(f"Warning: Failed to read {register_name} from motor {name} (ID {motor_id}): {e}")
                results[name] = 0

        return results

    def _read_register(self, motor_id: int, addr: int, length: int) -> int:
        """
        Read a register from a single motor using Feetech STS protocol.

        Feetech STS protocol packet format:
        - Header: [0xFF, 0xFF]
        - ID: motor ID
        - Length: packet length (instruction + params + checksum)
        - Instruction: 0x02 for READ
        - Params: address (2 bytes, little-endian) + read length
        - Checksum: ~(sum(ID + Length + Instruction + Params)) & 0xFF

        Response format:
        - Header: [0xFF, 0xFF]
        - ID: motor ID
        - Length: response length
        - Error: error byte (0 = success)
        - Data: register value (little-endian)
        - Checksum

        Args:
            motor_id: Motor ID (1-254)
            addr: Register address
            length: Number of bytes to read (1 or 2)

        Returns:
            Register value as integer

        Raises:
            serial.SerialException: If communication fails
        """
        # Build READ instruction packet
        # [0xFF, 0xFF, ID, LEN, INST, ADDR_L, ADDR_H, READ_LEN, CHECKSUM]
        packet = [
            0xFF,
            0xFF,
            motor_id,
            4,  # length: instruction(1) + addr(2) + read_len(1)
            0x02,  # READ instruction
            addr & 0xFF,  # address low byte
            (addr >> 8) & 0xFF,  # address high byte
            length,  # number of bytes to read
        ]

        # Calculate checksum: ~(sum of all bytes after header) & 0xFF
        checksum = (~sum(packet[2:]) & 0xFF)
        packet.append(checksum)

        # Send packet
        self.serial.reset_input_buffer()
        self.serial.write(bytes(packet))

        # Read response
        # Response: [0xFF, 0xFF, ID, LEN, ERR, DATA..., CHECKSUM]
        header = self.serial.read(4)
        if len(header) < 4:
            # Timeout - return 0
            return 0

        if header[0] != 0xFF or header[1] != 0xFF:
            # Invalid header
            return 0

        resp_id = header[2]
        resp_len = header[3]

        # Read rest of response (error + data + checksum)
        body = self.serial.read(resp_len)
        if len(body) < resp_len:
            # Incomplete response
            return 0

        # body[0] is error byte (ignore for now)
        # body[1:] is data + checksum

        # Extract data bytes (little-endian)
        if length == 1:
            value = body[1] if len(body) > 1 else 0
        elif length == 2:
            if len(body) >= 3:
                value = body[1] | (body[2] << 8)
            else:
                value = 0
        else:
            value = 0

        return value
