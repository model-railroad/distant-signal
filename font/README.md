Source of font files:


## `swetland-vt100` font:

3x5 [VT100 font by Brian Swetland](https://vt100.tarunz.org/):
- https://vt100.tarunz.org/font.gif
- License is ["MIT-like"](https://vt100.tarunz.org/LICENSE).

Converted to BDF using [Fony 1.4.7-WIP](http://hukka.ncn.fi/?fony)
although that BDF won't load using `adafruit_bitmap_font` as-is.


## `tom-thumb` font:

3x5 [Tom Thumb by Robey](https://robey.lag.net/2010/01/23/tiny-monospace-font.html)
- https://robey.lag.net/downloads/tom-thumb.bdf
- License is [CC0](https://creativecommons.org/public-domain/cc0/) or [CC-BY 3.0](https://creativecommons.org/licenses/by/3.0/deed.en)


The file `tom-thumb2.bdf` is a fork of `tom-thumb.bdf` where the
digits 0-9 are recreated using Swetland's VT100 "blocky" digits.
IMHO they are much more readable with a small 3x5 size.

~~

