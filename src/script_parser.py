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

import displayio
import json
import re
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

class ScriptParser:
    def __init__(self, sx: int, sy: int, fonts):
        self._sx = sx
        self._sy = sy
        self._root = displayio.Group()
        self._title = displayio.Group()
        self._blocks = {}
        self._states = {}
        self._fonts = fonts
        self._palettes = {}

    def _clearGroup(self, group) -> None:
        while group:
            group.pop()

    def reset(self) -> None:
        self._clearGroup(self._title)
        self._blocks.clear()
        self._states.clear()
        self._clearGroup(self._root)
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

    def _parseInt(self, s:str|int, sxy:int = 0, offset:int = 0) -> int:
        res = offset
        if isinstance(s, int):
            res += s
        else:
            # We don't have re.split("([+-])", str) on CircuitPython
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
        if sxy > 0:
            while res < 0:
                res += sxy
            while res > sxy:
                res -= sxy
        return res

    def _parseX(self, s:str, offset:int = 0) -> int:
        return self._parseInt(s, self._sx, offset)

    def _parseY(self, s:str, offset:int = 0) -> int:
        return self._parseInt(s, self._sy, offset)

    def _parseInstructions(self, destGroup, jsonObj, instructions, vars, ofx:int, ofy:int):
        # "instructions" is a list (array) of "instruction" (a dict with key/values)
        for instruction in instructions:
            # Are variables used?
            has_var = False
            for k, v in instruction.items():
                if v in vars:
                    has_var = True
                    break
            if has_var:
                # Dup the instruction to avoid expanding the template in the original object
                instruction = dict(instruction)
                # Expand vars in the duplicated instruction
                for k, v in instruction.items():
                    if v in vars:
                        instruction[k] = vars[v]
            if "tmpl" in instruction:
                tmpl_name = instruction["tmpl"]
                tmpl_insts = jsonObj[tmpl_name]
                tmpl_vars = dict(vars)
                tmpl_vars.update(instruction["vars"])
                tmpl_ofx = self._parseInt(instruction["x"], offset=ofx)
                tmpl_ofy = self._parseInt(instruction["y"], offset=ofy)
                print("@@ templ_ofy", instruction["y"], "+", ofy, "=>",tmpl_ofy )
                self._parseInstructions(destGroup, jsonObj, tmpl_insts, tmpl_vars, tmpl_ofx, tmpl_ofy)

            elif "op" in instruction:
                op = instruction["op"]

                if op == "line":
                    rgb = Rgb(instruction["rgb"])
                    x1 = self._parseX(instruction["x1"], ofx)
                    y1 = self._parseY(instruction["y1"], ofy)
                    x2 = self._parseX(instruction["x2"], ofx)
                    y2 = self._parseY(instruction["y2"], ofy)
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
                    destGroup.append(p)

                elif op == "poly":
                    rgb = Rgb(instruction["rgb"])
                    ptsOjb = instruction["pts"]
                    pts = []
                    for pt in ptsOjb:
                        x = self._parseX(pt["x"], ofx)
                        y = self._parseY(pt["y"], ofy)
                        pts.append( (x, y) )
                    p = vectorio.Polygon(
                        pixel_shader=self._getPalette(rgb),
                        x=0,
                        y=0,
                        points=pts
                    )
                    destGroup.append(p)

                elif op == "rect":
                    rgb = Rgb(instruction["rgb"])
                    x = self._parseX(instruction["x"], ofx)
                    y = self._parseY(instruction["y"], ofy)
                    w = self._parseX(instruction["w"])
                    h = self._parseY(instruction["h"])
                    r = vectorio.Rectangle(
                        pixel_shader=self._getPalette(rgb),
                        x=x,
                        y=y,
                        width=w,
                        height=h,
                    )
                    destGroup.append(r)

                elif op == "text":
                    rgb = Rgb(instruction["rgb"])
                    x = self._parseX(instruction["x"], ofx)
                    y = self._parseY(instruction["y"], ofy)
                    txt = str(instruction["t"])
                    scale = int(instruction.get("scale", 1))
                    font_index = int(instruction.get("font", 1))

                    t = Label(self._fonts[font_index % len(self._fonts)])
                    t.x = x
                    t.y = y + FONT_Y_OFFSET * scale
                    t.scale = scale
                    t.text = txt
                    t.color = rgb.asHex()
                    destGroup.append(t)

    def _parseGroup(self, jsonObj, instructions):
        group = displayio.Group()
        group.hidden = True
        self._parseInstructions(group, jsonObj, instructions, {}, 0, 0)
        return group

    def parseJson(self, jsonStr:str) -> None:
        self.reset()
        jsonObj = json.loads(jsonStr)

        if "title" in jsonObj:
            self._title = self._parseGroup(jsonObj, jsonObj["title"])
            self._root.append(self._title)
            self._title.hidden = False

        if "states" in jsonObj:
            for state_key in jsonObj["states"]:
                insts = jsonObj["states"][state_key]
                group = self._parseGroup(jsonObj, insts)
                self._states[state_key] = group
                self._root.append(group)

        if "blocks" in jsonObj:
            for block_key in jsonObj["blocks"]:
                b = jsonObj["blocks"][block_key]
                groups = {
                    "active"  : self._parseGroup(jsonObj, b["active"]),
                    "inactive": self._parseGroup(jsonObj, b["inactive"]),
                }
                self._blocks[block_key] = groups
                self._root.append(groups["active"])
                self._root.append(groups["inactive"])

    def display(self, display, activeState="", activeBlocks=[]):
        for state_key in self._states:
            self._states[state_key].hidden = state_key != activeState
        for block_key in self._blocks:
            b = self._blocks[block_key]
            is_block_active = block_key in activeBlocks
            b["active"].hidden = not is_block_active
            b["inactive"].hidden = is_block_active
        display.root_group = self._root


#~~


