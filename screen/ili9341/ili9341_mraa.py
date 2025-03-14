"""This module implements a pure python driver for spi-connected ILI9341 LCD
display, using `mraa` GPIO library.

"""

import time
import mraa

from .ili9341_base import Ili9341Base


class Ili9341Mraa(Ili9341Base):
    """Class to manipulate ILI9341 SPI displays using eclipse/mraa library."""

    def __init__(
            self,
            spi_id,
            dcx_pin_id,
            rst_pin_id=None,
            spi_clock_hz=42_000_000,
            **kwargs):
        """Initialize Ili9341Mraa class.

        Args:

        - spi_id: (int) Mraa SPI device ID.

        - dcx_pin_id: (int) Mraa GPIO pin id for the DC/X pin. This is not GPIO
          number, rather the board/machine pin id shown on the leftmost column
          of `mraa-gpio list`.

        - rst_pin_id: (int) Mraa GPIO pin id for the RST pin. Can be set to
          `None` if hardware reset is not used (the pin is connected to +3.3V).

        - spi_clock_hz: (int) Desired speed of the SPI clock, in Hz.

        - Extra keyword arguments are forwarded to `Ili9341Base` class.

        """
        # Create SPI device.
        self._spi = mraa.Spi(spi_id)
        self._spi.mode(0)  # SPI mode 0.
        self._spi.lsbmode(False)  # MSB first.
        self._spi.frequency(spi_clock_hz)

        # Create GPIO interface for data/control select line.
        self._dcx_pin = mraa.Gpio(dcx_pin_id)
        self._dcx_pin.dir(mraa.DIR_OUT)

        # Create GPIO interface for reset line, if given.
        if rst_pin_id is not None:
            self._rst_pin = mraa.Gpio(rst_pin_id)
            self._rst_pin.dir(mraa.DIR_OUT)
        else:
            self._rst_pin = None

        super().__init__(**kwargs)

    def _spi_write(self, buff):
        self._spi.write(buff)

    def _switch_to_ctrl_mode(self):
        self._dcx_pin.write(0)

    def _switch_to_data_mode(self):
        self._dcx_pin.write(1)

    def _do_hardware_reset(self):
        if self._rst_pin is not None:
            self._rst_pin.write(1)
            time.sleep(0.005)
            self._rst_pin.write(0)
            time.sleep(0.02)
            self._rst_pin.write(1)
            time.sleep(0.150)
