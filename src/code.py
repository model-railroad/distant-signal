# Lights Test
# 2024 (c) ralfoide at gmail
# License: MIT
#
# Target Platform: CircuitPython 9.x on AdaFruit QT PY ESP32-S2
#
# Hardware:
# - AdaFruit QT PY ESP32-S2
# - 2x 100 LEDs WS2812B addressable fairy light strings (source https://amzn.to/40UGURS)
# - LED string connected to GND and 5V on the QT PY.
# - LED string 1 and 2 connected in parallel to A1 pin on QT PY.


import adafruit_connection_manager
import adafruit_logging as logging
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import board
import digitalio
import neopixel
import os
import time
import wifi
import sequencer

_led = None
_neo = None
_mqtt = None
_boot_btn = None
_logger = logging.getLogger("Ambiance")
_logger.setLevel(logging.DEBUG)

NEO_LEN = 100

COL_OFF = (0, 0, 0)
COL_RED = (255, 0, 0)
COL_GREEN = (0, 255, 0)
COL_BLUE = (0, 0, 255)
COL_ORANGE = (255, 40, 0)

MQTT_TOPIC_SUBSCRIPTION  = "ambiance/#"
MQTT_TOPIC_SCRIPT_INIT   = "ambiance/script/init"
MQTT_TOPIC_SCRIPT_EVENT  = "ambiance/script/event"
MQTT_TOPIC_EVENT_TRIGGER = "ambiance/event/trigger"


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
    global _mqtt
    host = os.getenv("MQTT_BROKER_IP")
    if not host:
        print("@@ MQTT: disabled")
        return
    port = int(os.getenv("MQTT_BROKER_PORT"))
    user = os.getenv("MQTT_USERNAME")
    pasw = os.getenv("MQTT_PASSWORD")
    print("@@ MQTT: connect to", host, ", port", port, ", user", user, "pass", pasw)

    # Source: https://adafruit-playground.com/u/justmobilize/pages/adafruit-connection-manager
    pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)

    # Source: https://learn.adafruit.com/mqtt-in-circuitpython/advanced-minimqtt-usage
    _mqtt = MQTT.MQTT(
        broker=host,
        #port=port,
        username=user,
        password=pasw,
        is_ssl=False,
        socket_pool=pool,
    )
    _mqtt.logger = _logger

    _mqtt.on_connect = _mqtt_on_connected
    _mqtt.on_disconnect = _mqtt_on_disconnected
    _mqtt.on_message = _mqtt_on_message

    print("@@ MQTT: connecting...")
    _mqtt.connect()

def _mqtt_on_connected(client, userdata, flags, rc):
    # This function will be called when the client is connected successfully to the broker.
    print("@Q MQTT: Connected")
    # Subscribe to all changes.
    client.subscribe(MQTT_TOPIC_SUBSCRIPTION)

def _mqtt_on_disconnected(client, userdata, rc):
    # This method is called when the client is disconnected
    print("@Q MQTT: Disconnected")

def _mqtt_on_message(client, topic, message):
    """Method callled when a client's subscribed feed has a new
    value.
    :param str topic: The topic of the feed with a new value.
    :param str message: The new value
    """
    print("@Q MQTT: New message on topic {topic}: {message}")

def _mqtt_loop():
    if not _mqtt:
        return
    try:
        _mqtt.loop()
    except (ValueError, RuntimeError) as e:
        print("@@ MQTT: Failed to get data, retrying\n", e)
        time.sleep(1)
        _mqtt.reconnect()


def blink() -> None:
    if time.time() % 2 == 0:
        _led.brightness = 0
    else:
        _led.brightness = 0.1


def loop() -> None:
    print("@@ loop")
    pass

    # # Sleep a few seconds at boot
    for i in range(0, 3):
        print(i)
        blink()
        time.sleep(1)

    _led.fill(COL_ORANGE)
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
        blink()
        _mqtt_loop()
        if not _boot_btn.value:
            seq.rerun()
        if not seq.step():
            time.sleep(0.25)


if __name__ == "__main__":
    init()
    init_wifi()
    init_mqtt()
    loop()

#~~
