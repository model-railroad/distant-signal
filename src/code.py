# Lights Test
# 2024 (c) ralfoide at gmail
# License: MIT
#
# Target Platform: CircuitPython 9.x on AdaFruit QT PY ESP32-S2

import board
import digitalio
import neopixel
import os
import time
import wifi
import sequencer

_led = None
_neo = None
_boot_btn = None

NEO_LEN = 100

COL_OFF = (0, 0, 0)
COL_RED = (255, 0, 0)
COL_GREEN = (0, 255, 0)
COL_BLUE = (0, 0, 255)
COL_ORANGE = (255, 40, 0)

COLS = [
    (0,  0, 0),
    (40,  0, 0),
    (80,  0, 0),
    (120, 0, 0),
    (160, 0, 0),
    (180, 0, 0),
    (220, 0, 0),
    (255, 0, 0),

    (0, 0,  0),
    (0, 40,  0),
    (0, 80,  0),
    (0, 120, 0),
    (0, 160, 0),
    (0, 180, 0),
    (0, 220, 0),
    (0, 255, 0),

    (0, 0, 0, ),
    (0, 0, 40 ),
    (0, 0, 80 ),
    (0, 0, 120),
    (0, 0, 160),
    (0, 0, 180),
    (0, 0, 220),
    (0, 0, 255),

    (255, 0, 0),
    (255, 40, 0),
    (255, 80, 0),
    (255, 120, 0),
    (255, 160, 0),
    (255, 180, 0),
    (255, 220, 0),
    (255, 255, 0),
]

def init() -> None:
    print("@@ init")
    global _led
    global _neo
    global _boot_btn
    _led = neopixel.NeoPixel(board.NEOPIXEL, 1)
    _led.brightness = 0.1
    _neo = neopixel.NeoPixel(board.A1, NEO_LEN, auto_write = False, pixel_order=(0, 1, 2))
    _neo.brightness = 1
    _boot_btn = digitalio.DigitalInOut(board.D0)
    _boot_btn.switch_to_input(pull = digitalio.Pull.UP)

def init_wifi() -> None:
    print("@@ WiFI setup")
    # Get wifi AP credentials from onboard settings.toml file
    wifi_ssid = os.getenv("CIRCUITPY_WIFI_SSID")
    wifi_password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
    print("@@ WiFI SSID:", wifi_ssid)
    if wifi_ssid is None:
        print("@@ WiFI credentials are kept in settings.toml, please add them there!")
        raise ValueError("WiFI SSID not found in environment variables")

    try:
        wifi.radio.connect(wifi_ssid, wifi_password)
    except ConnectionError:
        print("@@ WiFI Failed to connect to WiFi with provided credentials")
        raise
    print("@@ WiFI OK for", wifi_ssid)

def init_mqtt() -> None:
    pass

_blink_idx = 0
def blink() -> None:
    global _blink_idx
    if _blink_idx:
        _led.brightness = 0
        _blink_idx = 1
    else:
        _led.brightness = 0.1
        _blink_idx = 0


def loop() -> None:
    print("@@ loop")
    pass

    # # Sleep a few seconds at boot
    for i in range(0, 3):
        print(i)
        blink()
        time.sleep(1)

    _led.fill(COL_GREEN)
    _neo.fill(COL_OFF)

    seq = sequencer.Sequencer(sequencer.NeoWrapper(_neo, NEO_LEN))

    blink()
    seq.parse("Fill #000000 1 ; SlowFill 0.1  #00FF00 10  #FF0000 10 ;")
    while seq.step():
        blink()

    seq.parse("Slide 0.1 80 ")
    while seq.step():
        blink()

    while True:
        if not _boot_btn.value:
            seq.rerun()
        if not seq.step():
            time.sleep(0.25)
            blink()


if __name__ == "__main__":
    init()
    init_wifi()
    init_mqtt()
    loop()

#~~
