## How to Use

1. **Install Required Libraries** (if not already installed on your Raspberry Pi):

```plaintext
sudo apt-get update
sudo apt-get install python3-gpiozero
```


2. **Make the Script Executable**:

```plaintext
chmod +x led_control.py
```


3. **Basic Usage**:

Turn the activity LED on:

```plaintext
sudo python3 led_control.py --pin act --on
```

Turn the activity LED off:

```plaintext
sudo python3 led_control.py --pin act --off
```

Blink the activity LED 10 times:

```plaintext
sudo python3 led_control.py --pin act --blink --count 10
```

Pulse the LED (if supported):

```plaintext
sudo python3 led_control.py --pin act --pulse --count 5
```

Flash a message in Morse code:

```plaintext
sudo python3 led_control.py --pin act --morse "SOS"
```




## Notes on Raspberry Pi LEDs

1. **Permissions**: You need to run the script with `sudo` to access GPIO pins.
2. **LED Pins**:

1. The activity LED (ACT) is typically on GPIO 47 on newer Pi models
2. The power LED (PWR) is on GPIO 35 on some models
3. These may vary depending on your Raspberry Pi model



3. **External LEDs**:

1. You can also control external LEDs connected to GPIO pins
2. Use `--pin 17` (or any valid GPIO number) for external LEDs



4. **Active High/Low**:

1. Some LEDs turn on when the pin is high (active high)
2. Others turn on when the pin is low (active low)
3. Use `--active-high` if your LED is active high



5. **PWM Support**:

1. The pulse feature requires PWM support
2. The internal ACT LED may not support PWM on all Pi models
3. The script will fall back to blinking if PWM is not supported





## Troubleshooting

1. **LED Not Responding**:

1. Try a different pin number for your specific Pi model
2. For the ACT LED, try pins 47, 16, or 42 depending on your Pi model
3. Make sure you're running with sudo



2. **Permission Errors**:

1. Always run with sudo: `sudo python3 led_control.py ...`



3. **Library Not Found**:

1. Install gpiozero: `sudo apt-get install python3-gpiozero`



4. **PWM Not Working**:

1. The internal LEDs may not support PWM on all Pi models
2. Try with an external LED connected to a PWM-capable GPIO pin





This script should give you full control over your Raspberry Pi's internal LEDs as well as any external LEDs you connect!