"""
Common SCPI instrument functionality for TCP/IP-based instrument communication.

This module provides a base class `SCPIInstrument` that handles the common
interaction with SCPI-compatible instruments over TCP/IP socket connections.

The class is designed to be inherited by specific instrument readers (like
`OscilloscopeReader` and `TemperatureHumidityReader`) and provides the
following functionality:

- TCP/IP socket connection management
- SCPI command sending and response receiving
- Timeout handling
- Command newline termination
- Resource cleanup on disconnection

This class does NOT depend on PyVISA and uses native Python socket operations
over TCP/IP.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import socket
import time
from typing import TYPE_CHECKING, Any, Optional

import pyvisa

import logging

logger = logging.getLogger(__name__)

from labpilot import config


class SCPIInstrument(ABC):
    """
    Base class for instruments that communicate via SCPI over TCP/IP.

    This class handles the common functionality for interacting with
    SCPI-compatible instruments connected via Ethernet (TCP/IP). It provides:

    - Socket connection management (connect/disconnect)
    - SCPI command sending with proper newline termination
    - Response reading (for queries like "?")
    - Timeout handling
    - Resource cleanup

    Attributes:
        IP (str): The IP address of the instrument.
        PORT (int): The TCP port of the instrument.
        SOCKET (Optional[socket.socket]): The underlying TCP socket.
        TIMEOUT (int): Command timeout in milliseconds.
    """

    IP: str
    TIMEOUT: int = 30000  # Default timeout: 30 seconds

    def __init__(self, name: str, ip: str) -> None:
        """
        Initialize the SCPI instrument.

        Args:
            name: Friendly Name of the instrument. This is a name for refering to it during execution of the program
            ip: The IP address of the instrument.
        """
        self.name = name
        self.IP = ip

        # Initialize Resource Manager
        self.rm = pyvisa.ResourceManager()

    @property
    def is_connected(self) -> bool:
        """
        Check if the instrument socket is connected.

        Returns:
            bool: True if connected, False otherwise.
        """
        return self.sds is not None

    def connect(self) -> bool:
        """
        Establish connection to the instrument.

        Creates a TCP socket and connects to the instrument's IP and port.

        Returns:
            bool: True if connection was successful.
        """
        try:
            self.sds = self.rm.open_resource(f"TCPIP::{self.IP}::INSTR")
            self.sds.timeout = 5000  # 5s
            self.sds.chunk_size = 20 * 1024 * 1024
            logger.debug(f"Connected to instrument at {self.IP}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to instrument at {self.IP}: {e}")
            self.sds = None
            return False

    def disconnect(self) -> None:
        """
        Close the connection to the instrument and clean up resources.

        Closes the socket if it exists.
        """
        if self.sds:
            try:
                self.sds.close()
                self.sds = None
                logger.info(f"{self.name} disconnected")
            except Exception as e:
                logger.warning(f"Error closing socket: {e}")

    def send_command(self, command: str) -> str:
        """
        Send an SCPI command to the instrument and optionally read the response.

        SCPI commands are sent as newline-terminated strings. Queries (ending with '?')
        or commands expecting a response will have their response read and returned.

        Args:
            command: The SCPI command to send (without newline).

        Returns:
            str: The response from the instrument (stripped), or empty string if no
                response was expected or if connection failed.

        Raises:
            socket.timeout: If the command or response times out.
            ConnectionError: If the connection is lost during communication.
        """
        if self.sds is None or not self.is_connected:
            return ""

        try:
            # Send the command with newline termination (SCPI protocol)
            self.sds.write(command)

            # Check if this is a query or a command expecting a response
            needs_response = "?" in command or command.endswith("DAT2")

            if needs_response:
                # Read the response
                raw_bytes = self.sds.read_raw().strip()

                logger.debug(f"SCPI command: {command}. Response: {raw_bytes.decode()}")
                return raw_bytes.decode()
            else:
                # Command with no response
                logger.debug(f"SCPI command: {command}. No response expected.")
                return ""
        except socket.timeout:
            logger.error(f"Command timed out: {command}")
            raise
        except ConnectionError as e:
            logger.error(f"Connection lost while sending command: {command}")
            self.disconnect()
            raise
        except Exception as e:
            logger.error(f"Error sending command {command}: {e}")
            raise

    def reset(self) -> None:
        """
        Send a reset command to the instrument.

        Sends the '*RST' command to reset the instrument to its default state.
        """
        self.send_command("*RST")

    def clear(self) -> None:
        """
        Clear all status and error flags on the instrument.

        Sends the '*CLS' command to clear status and error registers.
        """
        self.send_command("*CLS")

    @abstractmethod
    def setup(self) -> None:
        """
        Execute a few initial configuration commands.

        Subclasses should override this method to implement their own
        initialization sequence. By default, this does nothing.
        """
        # Default implementation: do nothing
        # Subclasses should override this for instrument-specific setup
        pass


# Type aliases for convenience
class SCPIInstrumentSocketMixin:
    """
    Mixin class for SCPI instruments that use socket connections.

    This is a marker class to indicate that a class uses socket-based
    communication with SCPI commands.
    """

    pass
