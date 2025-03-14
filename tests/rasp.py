#!/usr/bin/env python3
"""
Raspberry Pi Internal LED Controller
-----------------------------------
This script allows you to control the onboard LED of a Raspberry Pi.
It works with the activity LED (ACT) that's available on most Pi models.
"""

import argparse
import time
import sys
from gpiozero import LED, Device
from gpiozero.pins.rpigpio import RPiGPIOFactory

# Default GPIO pin for the activity LED on most Raspberry Pi models
# This may vary depending on your Pi model
ACT_LED_PIN = 47  # For Raspberry Pi 3B+, 4, etc.

# Alternative pins for different Pi models
LED_PINS = {
    "act": 47,  # Activity LED on newer Pi models
    "pwr": 35,  # Power LED on some Pi models (may not be controllable)
    "0": 17,  # Regular GPIO pins if you want to connect an external LED
    "1": 18,
    "2": 27,
    "3": 22
}


def setup_led(pin, active_high=False):
    """Set up the LED with the specified pin."""
    try:
        # Use RPiGPIOFactory to ensure we're using the RPi.GPIO backend
        factory = RPiGPIOFactory()
        led = LED(pin, active_high=active_high, pin_factory=factory)
        return led
    except Exception as e:
        print(f"Error setting up LED on pin {pin}: {e}")
        print("This script must be run on a Raspberry Pi with gpiozero installed.")
        print("Install with: sudo apt-get install python3-gpiozero")
        sys.exit(1)


def turn_on(led):
    """Turn the LED on."""
    led.on()
    print(f"LED turned ON")


def turn_off(led):
    """Turn the LED off."""
    led.off()
    print(f"LED turned OFF")


def blink(led, count, on_time, off_time):
    """Blink the LED the specified number of times."""
    print(f"Blinking LED {count} times (on: {on_time}s, off: {off_time}s)")

    for i in range(count):
        led.on()
        time.sleep(on_time)
        led.off()
        time.sleep(off_time)
        sys.stdout.write(f"\rBlink {i + 1}/{count}")
        sys.stdout.flush()

    print("\nBlinking complete")


def pulse(led, count, fade_time):
    """Pulse the LED by gradually changing brightness."""
    print(f"Pulsing LED {count} times (fade time: {fade_time}s)")

    # Note: This only works if the LED pin supports PWM
    # The internal ACT LED may not support PWM on all Pi models
    try:
        for i in range(count):
            # Fade in
            for brightness in range(0, 101, 5):
                led.value = brightness / 100
                time.sleep(fade_time / 40)

            # Fade out
            for brightness in range(100, -1, -5):
                led.value = brightness / 100
                time.sleep(fade_time / 40)

            sys.stdout.write(f"\rPulse {i + 1}/{count}")
            sys.stdout.flush()

        print("\nPulsing complete")
    except AttributeError:
        print("Warning: This LED doesn't support brightness control. Using regular blink instead.")
        blink(led, count, fade_time / 2, fade_time / 2)


def morse_code(led, message, unit=0.1):
    """Flash the LED in Morse code for the given message."""
    morse_dict = {
        'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
        'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
        'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
        'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
        'Y': '-.--', 'Z': '--..', '0': '-----', '1': '.----', '2': '..---',
        '3': '...--', '4': '....-', '5': '.....', '6': '-....', '7': '--...',
        '8': '---..', '9': '----.', ' ': '/'
    }

    print(f"Flashing message in Morse code: {message}")

    for char in message.upper():
        if char in morse_dict:
            code = morse_dict[char]
            print(f"{char}: {code}")

            for symbol in code:
                if symbol == '.':
                    led.on()
                    time.sleep(unit)
                elif symbol == '-':
                    led.on()
                    time.sleep(3 * unit)
                elif symbol == '/':
                    time.sleep(7 * unit)  # Space between words

                led.off()
                time.sleep(unit)  # Space between symbols

            time.sleep(3 * unit)  # Space between letters

    print("Morse code transmission complete")


def main():
    parser = argparse.ArgumentParser(description="Control Raspberry Pi onboard LED")

    # LED selection
    parser.add_argument("--pin", default="act",
                        help="GPIO pin number or name (act, pwr, 0, 1, 2, 3)")

    # LED state
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--on", action="store_true", help="Turn the LED on")
    group.add_argument("--off", action="store_true", help="Turn the LED off")
    group.add_argument("--blink", action="store_true", help="Blink the LED")
    group.add_argument("--pulse", action="store_true", help="Pulse the LED (if supported)")
    group.add_argument("--morse", help="Flash a message in Morse code")

    # Blink parameters
    parser.add_argument("--count", type=int, default=5, help="Number of blinks/pulses")
    parser.add_argument("--on-time", type=float, default=0.5, help="Time in seconds for LED to stay on")
    parser.add_argument("--off-time", type=float, default=0.5, help="Time in seconds for LED to stay off")
    parser.add_argument("--fade-time", type=float, default=1.0, help="Time in seconds for LED to fade in/out")

    # Active high/low setting
    parser.add_argument("--active-high", action="store_true",
                        help="Set if LED is active high (on when pin is high)")

    args = parser.parse_args()

    # Determine the pin number
    pin = args.pin
    if pin in LED_PINS:
        pin = LED_PINS[pin]
    else:
        try:
            pin = int(pin)
        except ValueError:
            print(f"Invalid pin: {pin}. Use a number or one of: {', '.join(LED_PINS.keys())}")
            sys.exit(1)

    # Set up the LED
    led = setup_led(pin, args.active_high)

    try:
        # Perform the requested action
        if args.on:
            turn_on(led)
        elif args.off:
            turn_off(led)
        elif args.blink:
            blink(led, args.count, args.on_time, args.off_time)
        elif args.pulse:
            pulse(led, args.count, args.fade_time)
        elif args.morse:
            morse_code(led, args.morse)

        # Keep the script running if the LED is on
        if args.on:
            print("Press Ctrl+C to exit")
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Clean up
        led.close()


if __name__ == "__main__":
    main()