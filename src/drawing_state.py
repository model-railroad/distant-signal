# Distant Signal
# 2025 (c) ralfoide at gmail
# License: MIT
#
# Parses a mini script that defines a screen rendering.
#
# Instructions available:
#
# Text:
# T x y "string" [#RRGGBB] [scale1|scale2] [font1|font2] ;
#
# Rect (filled):
# R x y w h [#RRGGBB] ;
#
# Line:
# L x y w h [#RRGGBB] ;
#
# Polygon (3 points or more):
# P x1 y1 x2 y2 x3 y3 [.. xN yN] [#RRGGBB] ;
#
# Negative x/y are relative to the end of the display.
# The last RGB / scale / font attribute is reused for follow up instructions.
#

import re
import displayio
import vectorio
from adafruit_display_text.label import Label

FONT_Y_OFFSET = 3

class Rgb:
    def __init__(self, rgb: str|Rgb):
        if isinstance(rgb, self.__class__):
            self.r = rgb.r
            self.g = rgb.g
            self.b = rgb.b
        else:
            if len(rgb) != 6 and len(rgb) != 7:
                raise ValueError("Sequencer: RGB expected in hex format [#?]RRGGBB but was '%s'" % rgb)
            if rgb.startswith("#"):
                rgb = rgb[1:]
            self.r = int(rgb[0:2], 16)
            self.g = int(rgb[2:4], 16)
            self.b = int(rgb[4:6], 16)

    def asTuple(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)

    def asHex(self) -> int:
        return (self.r << 16) + (self.g << 8) + (self.b)

    def __eq__(self, rhs):
        if not isinstance(rhs, self.__class__):
            return NotImplemented
        return (self.r == rhs.r
            and self.g == rhs.g
            and self.b == rhs.b)

    def __repr__(self):
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

class DrawingState:
    def __init__(self, sx: int, sy: int, fonts):
        self._sx = sx
        self._sy = sy
        self._group = displayio.Group()
        self._fonts = fonts
        self._palettes = {}

    def reset(self) -> None:
        self._group.hidden = True
        while self._group:
            self._group.pop()
        self._palettes.clear()

    def _getPalette(self, rgb: Rgb):
        rgb_val = rgb.asHex()
        if rgb_val in self._palettes:
            return self._palettes[rgb_val]
        else:
            pal = displayio.Palette(1)
            pal[0] = rgb_val
            self._palettes[rgb_val] = pal
            return pal

    def _parseInt(self, s:str, sxy:int) -> int:
        # We don't have re.split("([+-])", str) on CircuitPython
        res = 0
        op = "+"
        accum = 0
        s += ";" # to end processing
        for c in s:
            if c.isdigit():
                # parsing an integer
                accum = accum * 10 + int(c)
            else:
                # done parsing integer, merge into result using
                # previous op
                if op == "+":
                    res += accum
                else:
                    res -= accum
                accum = 0
                # parse next op, or ignore foreign character
                if c == "+" or c == "-":
                    op = c
        # Fix range to [0..sxy[
        while res < 0:
            res += sxy
        while res > sxy:
            res -= sxy
        return res

    def _parseX(self, s:str) -> int:
        return self._parseInt(s, self._sx)

    def _parseY(self, s:str) -> int:
        return self._parseInt(s, self._sy)

    def parse(self, instructions: str) -> None:
        self.reset()
        rgb = Rgb("#FFFFFF")
        scale = 1
        font_index = 0
        for line in instructions.split(";"):
            # Strip any whitespace (\n, \r, \t)
            lexems = [ x.strip() for x in line.strip().split(" ") if x.strip() and not x.isspace() ]
            if not lexems or lexems[0].startswith("#"):
                # Skip empty line or comment.
                continue
            line = " ".join(lexems)
            def lexpop():
                return lexems.pop(0)
            verb = lexpop().lower()
            lx = len(lexems)
            if verb == "l":
                # Line: L x1 y1 x2 y2 [#RRGGBB] ;
                if lx < 4 or lx > 5:
                    raise ValueError(f"Sequencer: Expected 'L' with 4-5 arguments in line '{line}'")
                x1 = self._parseX(lexpop())
                y1 = self._parseY(lexpop())
                x2 = self._parseX(lexpop())
                y2 = self._parseY(lexpop())
                if lexems:
                    rgb = Rgb(lexpop())

                w = x2-x1
                h = y2-y1
                if h == 0:
                    pts = [ (0,-1), (0,1), (w,h+1), (w,h-1) ]
                else:
                    pts = [ (-1,0), (1,0), (w+1,h), (w-1,h) ]
                p = vectorio.Polygon(
                    pixel_shader=self._getPalette(rgb),
                    x=x1,
                    y=y1,
                    points=pts
                )
                self._group.append(p)

            elif verb == "p":
                # Polygon (3 points or more): P x1 y1 x2 y2 x3 y3 [.. xN yN] [#RRGGBB] ;
                if lx < 6:
                    raise ValueError(f"Sequencer: Expected 'P' with 6+ arguments in line '{line}'")
                pts = []
                x1 = self._parseX(lexpop())
                y1 = self._parseY(lexpop())
                pts.append( (0,0) )
                for i in range(1, 3):
                    x = self._parseX(lexpop())
                    y = self._parseY(lexpop())
                    pts.append( (x - x1, y - y1) )

                tmpX = None
                while lexems:
                    opt = lexpop()
                    if opt.startswith("#"):
                        rgb = Rgb(opt)
                        break
                    elif tmpX is None:
                        tmpX = self._parseX(opt)
                    else:
                        y = self._parseY(opt)
                        pts.append( (tmpX - x1, y - y1) )
                        tmpX = None

                p = vectorio.Polygon(
                    pixel_shader=self._getPalette(rgb),
                    x=x1,
                    y=y1,
                    points=pts
                )
                self._group.append(p)

            elif verb == "r":
                # Rect (filled): R x y w h [#RRGGBB] ;
                if lx < 4 or lx > 5:
                    raise ValueError(f"Sequencer: Expected 'R' with 4-5 arguments in line '{line}'")
                x = self._parseX(lexpop())
                y = self._parseY(lexpop())
                w = self._parseX(lexpop())
                h = self._parseY(lexpop())
                if lexems:
                    rgb = Rgb(lexpop())

                r = vectorio.Rectangle(
                    pixel_shader=self._getPalette(rgb),
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                )
                self._group.append(r)

            elif verb == "t":
                # Text: T x y "string" [#RRGGBB] [scale1|scale2] [font1|font2] ;
                if lx < 3 or lx > 6:
                    raise ValueError(f"Sequencer: Expected 'T' with 3-6 arguments in line '{line}'")
                x = self._parseX(lexpop())
                y = self._parseY(lexpop())

                s = lexpop()
                if s.startswith('"'):
                    s = s[1:]
                    if s.endswith('"'):
                        s = s[:-1]
                    else:
                        while lexems:
                            s2 = lexpop()
                            if s2.endswith('"'):
                                s2 = s2[:-1]
                                s += " " + s2
                                break
                            else:
                                s += " " + s2

                while lexems:
                    opt = lexpop()
                    if opt.startswith("#"):
                        rgb = Rgb(opt)
                    elif opt.startswith("scale"):
                        sc = int(opt[5:])
                        scale = max(1, min(2, sc))
                    elif opt.startswith("font"):
                        idx = int(opt[4:])
                        font_index = max(1, min(2, idx)) - 1

                t = Label(self._fonts[font_index % len(self._fonts)])
                t.x = x
                t.y = y + FONT_Y_OFFSET * scale
                t.scale = scale
                t.text = s
                t.color = rgb.asHex()
                self._group.append(t)

            else:
                raise ValueError("DrawParser: Unknown verb '%s' in line '%s'" % (verb, line))

    def display(self, display):
        self._group.hidden = False
        display.root_group = self._group


#~~


