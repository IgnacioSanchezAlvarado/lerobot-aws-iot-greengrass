"""
Feetech STS3215 control table definitions.

Register addresses and data lengths for the STS3215 servo.
"""

# STS3215 control table: {register_name: (address, length_in_bytes)}
STS3215_CONTROL_TABLE = {
    # Read-only status registers
    "Present_Position": (56, 2),
    "Present_Velocity": (58, 2),
    "Present_Load": (60, 2),
    "Present_Temperature": (63, 1),
    "Present_Current": (69, 2),
    # Commonly used control registers
    "Goal_Position": (42, 2),
    "Torque_Enable": (40, 1),
    "ID": (5, 1),
    "Baud_Rate": (6, 1),
    "Model": (0, 2),
}

# Model-specific constants
MODEL_RESOLUTION = {
    "sts3215": 4096,  # 12-bit resolution (0-4095)
}

MODEL_BAUDRATE = {
    "sts3215": 1000000,  # 1 Mbps
}
