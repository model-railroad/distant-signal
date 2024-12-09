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

_led = None
_neo = None
_boot_btn = None

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
    _neo = neopixel.NeoPixel(board.A1, 100, auto_write = False, pixel_order=(0, 1, 2))
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

def loop() -> None:
    print("@@ loop")
    pass

    # # Sleep a few seconds at boot
    # for i in range(0, 3):
    #     print(i)
    #     set_neopixels(i % 2 == 0, 0)
    #     time.sleep(1)

    _led.fill(COL_GREEN)

    i = 0
    n = 0
    ic = 0
    effect = 3
    while True:
        _led.brightness = 0.1 if i & 2 == 0 else 0
        # _led.fill(COL_RED)
        # time.sleep(0.5)
        # _led.fill(COL_GREEN)
        # time.sleep(0.5)
        # _led.fill(COL_BLUE)
        # time.sleep(0.5)
        # _led.brightness = 0

        print(effect, i)

        # Cycle through COLS
        if effect == 0:
            c = COLS[ic]
            _neo.fill(c)
            _neo.show()
            ic = (ic+1) % len(COLS)
            print(ic, c)
            time.sleep(0.25)

        # Orange chase
        elif effect == 1:
            for j in range(0, 100):
                _neo[j] = COL_ORANGE if (j >= i and j <= i+10) else COL_OFF
            _neo.show()
            i = (i + 1) % (100 - 10)
            time.sleep(0.1)
        
        # Green Red Chase
        elif effect == 2:
            for j in range(0, 100):
                _neo[j] = COL_GREEN if (i + j) % 20 > 10 else COL_RED
            _neo.show()
            i = (i + 1) % 100
            time.sleep(0.1)

        # Green Red Static
        elif effect == 3:
            for j in range(0, 100):
                _neo[j] = COL_RED if (0 + j) % 20 > 10 else COL_GREEN
            _neo.show()
            i = i + 1
            #time.sleep(0.1)
            effect = 4

        elif effect == 4:
            i = i + 1
            time.sleep(0.1)

        elif effect == 5:
            for j in range(0, 100):
                _neo[j] = COL_RED if (i + j) % 20 > 10 else COL_GREEN
            _neo.show()
            i = i - 1
            time.sleep(0.1)

        n = n + 1
        if effect == 4:
            if not _boot_btn.value:
                effect = 5
                i = 0
                n = 0
        elif effect == 5 and n >= 80:
            effect = 3
            n = 0
            i = 0
        elif (effect == 0 and n > 8) or (effect > 0 and effect <= 2 and n > 32):
            effect = (effect + 1) % 3
            n = 0

if __name__ == "__main__":
    init()
    init_wifi()
    init_mqtt()
    loop()


