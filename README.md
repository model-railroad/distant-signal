# Ambiance

**Ambiance** is a CircuitPython script for an ESP32 to animate a pattern of LEDs on
an addressable pixel fairy string.
A small custom language allows one to define a
repeated sequence of RGB colors, and then animate it with a simple trigger.
The color and animation script can be loaded from an MQTT broker.


[<p align=center><img src="distrib/demo_thumbnail.jpg" alt="Ambiance Demonstration as deployed at the Randall Museum" style="width:50%; height:auto;"></p>](https://youtu.be/LdthG7FvIyU "Ambiance Experiment")


## Hardware used for this project

- AdaFruit QT PY ESP32-S2
- 2x 100 LEDs WS2812B addressable fairy light strings (such as https://amzn.to/40UGURS)
- LED string connected to GND and 5V on the QT PY.
- LED string 1 and 2 connected in parallel to A1 pin on QT PY.

The script is fairly customizable. Any NeoPixel or WS2812B-compatible LED strip should
work. The length of the LED strip can be customized.


## MQTT Interaction

**Ambiance** is used by the 
[Randall Train Automation Controller](https://www.alfray.com/trains/randall/rtac.html)
software via MQTT.
The automation controller publishes "color scripts" via MQTT topics, which are then
fetched and executed by the ESP32.

When used with the train automation controller, two colors scripts are used:

- An initial color pattern is executed when the train layout powers up.
  Once executed, the color pattern is static and does not change.
- A short color animation happens when a train starts its automatic run.
  This is done by defining an "event script" and a separate "event trigger".

The following MQTT topics are used:

- `ambiance/length`: The number of LEDs to fill and animate. This is currently set to a 100
  based on the fairy string currently used. Changing this topic on the MQTT broker allows to
  easily reconfigure the ESP32 program without having to upload a new sketch.

- `ambiance/brightness`: A float in the range 0..1. 0 corresponds to all LEDs off, and 1
  corresponds to maximum brightness.

- `ambiance/script/init`: The color script executed when the ESP32 starts.
  This script is executed as soon as it changes. 
  If the same script is sent twice in a row, it is executed only once.

- `ambiance/script/event`: The script executed for animation events.
  This script does not execute immediately.
  It only executes when the `event/trigger` topic is set.

- `ambiance/event/trigger`: The trigger for the event script.
  Any value different than the last one provided triggers the execution of the event script.




## LED Color Light Sequencer


An addressable LED string acts as a linear buffer of RGB values: a maximum number of
"pixels" can be controlled, each with an individual RGB color.

The number of LEDs in the string is configued by `NEO_LEN` in `code.py` and can be
overwritten using the `Lenght` instruction in the script (see below).

Often Arduino or ESP32 projects simply hardcode LED RGB values in their program, and
one needs to recompile and upload a new program to change the color pattern.

The main goal of **Ambiance** is to make it easy to change that color pattern:
the **Sequencer** reads a simple text-based scripting language that defines the color
patterns to use to fill the LED string, and how to animate it.

### Script syntax

- All instructions are separated by a semi-colon.
- An instruction beginning with # is a comment and ignored (till EOL or ;)
- Instructions are case-insensitive.
- RGB colors must be in the pattern #RRGGBB or RRGGBB. The # is optional.

### Control Instructions

`Length int ;`

This instuctions sets the number of the specified integer. Must be > 0 and < the maximum
buffer size compiled in the program (`NEO_LEN` in `code.py`, which defaults to 100).

`Brightness float ;`

This instruction sets the LED brightness, between 0 (off) and 1 (full brightness).
Note that the luminosity granularity depends on the LEDs being used. Default is 1.


## Color Filling Instructions

`Fill RGB1 Count1 [RGB2 Count2 ... RGBn Countn]`

This instruction fills the LED buffer _instantly_  with a _repeated_ pattern of
the color list given.

The count number does not need to match the length of the LED string (as defined
by the `Length` instruction): the pattern automatically repeats as many times as needed
to fill the LED buffer.

`SlowFill Delay RGB1 Count1 [RGB2 Count2 ... RGBn Countn]`

This is the same as the `Fill` instruction except the buffer is filled slowly with
a "delay" pause between each LED. The delay is a float representing seconds.


# Color Aninmation Instructions

`Slide Delay Count`

This instruction "slides" all the LED colors in the buffer by the `count` number,
with a pause in between each LED shifting. Essentially the delay controls the speed of the effect. The delay is a float representing seconds.

A delay value of zero is invalid.

When the delay is positive, the colors shift from the beginning towards the end of
the LED string.
If the delay is negative, it reverses the direction of the slide/shift effect;
the colors shift from the end towards the beginning of the LED string.


### Example Effects

Xmas colors:
```
"Fill #000000 1 ; SlowFill 0.1 #00FF00 10 #FF0000 10 ; Slide 0.1 80 "
```

* `Fill #000000 1` quick "erases" all colors and thus turns off all LEDs in the string.
* `SlowFill` then progressively make the colors re-appear, one by one.
  There is a repeated pattern of 10 green LEDs followed by 10 red LEDs.
  On a 100-LED string, the pattern is thus repeated 4 times.
* `Slide 0.1 80` shifts the colors 80 times. Since this is a multiple of the fill pattern
  length (10 green + 10 red = 20 LEDs), this gives the impressive that the green/red
  colors move 4 times and then end up in the same position.
  With a delay of 0.1 seconds and 80 iterations, the animation lasts 8 seconds.


Halloween colors:
```
"Fill #000000 1 ; SlowFill 0.1 #FF1000 40 #FF4000 10 ; Slide 0.1 100"
```

* `Fill #000000 1` quick "erases" all colors and thus turns off all LEDs in the string.
* `SlowFill` then progressively make the colors re-appear, one by one.
  There is a repeated pattern of 40 orange LEDs followed by 10 yellow LEDs.
  On a 100-LED string, the pattern is thus repeated twice.
* `Slide 0.05 100` shifts the colors 100 times. Since this is the size of the LED string
  pattern, the animation ends in the same state that it started.
  With a delay of 0.05 seconds and 100 iterations, the animation lasts 5 seconds.


### Usage As a Library

The **Sequencer** can be used as a standalone library:

```
neo = neopixel.NeoPixel(board.A1, NEO_LEN, auto_write = False, pixel_order=(0, 1, 2))
seq = sequencer.Sequencer(sequencer.NeoWrapper(neo, NEO_LEN))
seq.parse(""" Fill #000000 1 ; 
              SlowFill 0.1  #00FF00 10  #FF0000 10 ;
              Slide 0.1 80 """)
while seq.step(): True
```


## License

License: MIT

https://opensource.org/license/mit

Copyright 2024 (c) ralfoide at gmail

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the “Software”), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons
to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.

~~
