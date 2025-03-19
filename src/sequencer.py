# LED NeoPixel Sequencer
# 2024 (c) ralfoide at gmail
# License: MIT
#
# Target Platform: CircuitPython 9.x on AdaFruit QT PY ESP32-S2
#
# Sequencer Instructions Programs:
# - All instructions are separated by a semi-colon.
# - An instruction beginning by # is a comment and ignored (till EOL or ;)
# - Instructions are case-insensitive.
# - RGB colors must be in the pattern #RRGGBB or RRGGBB. The # is optional.
# Sequencer Instructions:
# - Length int ==> sets the number of the specified integer. Must be > 0 and < max.
#       Default is max as set in the constructor.
# - Brightness float ==> Sets the LED brightness, between 0 (off) and 1 (full brightness).
#       Note that the luminosity granularity depends on the LEDs being used. Default is 1.
# - Fill RGB1 Count1 [RGB2 Count2 ... RGBn Countn] ==> Fills the LED buffer with
#       a _repeated_ pattern of the color list given.
# - SlowFill Delay RGB1 Count1 [RGB2 Count2 ... RGBn Countn] ==> Same as "Fill"
#       but with a pause between each LED. The delay is a float representing seconds.
# - Slide Delay Count ==> Slides all the LED colors in the buffer by the indicated
#       count, with a pause between each LED. The delay is a float representing seconds.
#
# Example usage:
# _neo = neopixel.NeoPixel(board.A1, NEO_LEN, auto_write = False, pixel_order=(0, 1, 2))
# seq = sequencer.Sequencer(sequencer.NeoWrapper(_neo, NEO_LEN))
# seq.parse(""" Fill #000000 1 ; 
#               SlowFill 0.1  #00FF00 10  #FF0000 10 ;
#               Slide 0.1 80 """)
# while seq.step(): True

import time

class NeoWrapper:
    def __init__(self, target, max_len):
        self.data = [ target[i] for i in range(0, max_len) ]
        self.max_len = max_len
        self.len = max_len
        self._target = target

    def copy(self):
        self._target[:] = self.data

    def show(self):
        self._target.show()

    def sleep(self, seconds: float):
        time.sleep(seconds)

    def brightness(self, value):
        self._target.brightness = value

class Rgb:
    def __init__(self, rgb: str):
        if len(rgb) != 6 and len(rgb) != 7:
            raise ValueError("Sequencer: RGB expected in hex format [#?]RRGGBB but was '%s'" % rgb)
        if rgb.startswith("#"):
            rgb = rgb[1:]
        self.r = int(rgb[0:2], 16)
        self.g = int(rgb[2:4], 16)
        self.b = int(rgb[4:6], 16)

    def asTuple(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)

    def __eq__(self, rhs):
        if not isinstance(rhs, self.__class__):
            return NotImplemented
        return (self.r == rhs.r
            and self.g == rhs.g
            and self.b == rhs.b)

    def __repr__(self):
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"


class RgbCount:
    def __init__(self, rgb: str, count: int):
        self.rgb = Rgb(rgb)
        self.count = count

    def __eq__(self, rhs):
        if not isinstance(rhs, self.__class__):
            return NotImplemented
        return (self.count == rhs.count
            and self.rgb == rhs.rgb)

    def __repr__(self):
        return f"<{self.rgb},{self.count}>"


class Instruction:
    def __init__(self, neo: NeoWrapper):
        self._neo = neo

    def start(self) -> "Instruction":
        return None

    def step(self) -> "Instruction":
        return None


class InstructionSlide(Instruction):
    def __init__(self, neo: NeoWrapper, delay_s: float, count: int):
        super().__init__(neo)
        self._delay_s = delay_s
        self._count = count
        self._data = None

    def __eq__(self, rhs):
        if not isinstance(rhs, self.__class__):
            return NotImplemented
        return (self._count == rhs._count
            and self._delay_s == rhs._delay_s)

    def __repr__(self):
        return f"Slide {self._delay_s} s x {self._count}"

    def start(self) -> Instruction:
        self._data = self._count
        return self.step()

    def step(self) -> Instruction:
        if self._data is None:
            return None
        count = self._data
        nl = self._neo.len
        delay_s = self._delay_s
        if delay_s < 0:
            delay_s = -delay_s
            first = self._neo.data[0]
            self._neo.data[0 : nl-1] = self._neo.data[1 : nl]
            self._neo.data[nl-1] = first
        else:
            last = self._neo.data[nl-1]
            self._neo.data[1 : nl] = self._neo.data[0 : nl-1]
            self._neo.data[0] = last
        self._neo.copy()
        self._neo.show()
        self._neo.sleep(delay_s)
        count -= 1
        if count > 0:
            self._data = count
            return self
        # This instruction is completed
        self._data = None
        return None


class InstructionFill(Instruction):
    def __init__(self, neo: NeoWrapper, delay_s: float, runs: list[RgbCount]):
        super().__init__(neo)
        self._delay_s = delay_s
        self._runs = runs
        self._data = None

    def __eq__(self, rhs):
        if not isinstance(rhs, self.__class__):
            return NotImplemented
        # runs_ok = all(x == y for x, y in zip(self._runs, rhs._runs))
        runs_ok = (self._runs == rhs._runs)
        return (runs_ok
            and self._delay_s == rhs._delay_s)

    def __repr__(self):
        return f"Fill {self._delay_s} s x {self._runs}"

    def start(self) -> Instruction:
        # Instant fill
        self._data = (0, 0, 0, None)
        if self._delay_s == 0:
            # Make it an instant fill, bypass delays
            while self._step():
                pass
            self._neo.copy()
            self._neo.show()
            # This instruction is completed
            return None
        else:
            # Just execute the first step with its delay
            return self.step()

    def _step(self) -> bool:
        if self._data is None:
            return False
        index, run_index, curr_count, curr_rgb = self._data
        if index >= self._neo.len:
            return False
        if curr_rgb is None:
            run_curr = self._runs[run_index]
            curr_rgb = run_curr.rgb.asTuple()
            curr_count = run_curr.count
            run_index += 1
            if run_index == len(self._runs):
                run_index = 0
        self._neo.data[index] = curr_rgb
        curr_count -= 1
        if curr_count <= 0:
            curr_rgb = None
        index += 1
        if index <= self._neo.len:
            self._data = (index, run_index, curr_count, curr_rgb)
            return True
        else:
            self._data = None
            return False

    def step(self) -> Instruction:
        if self._data is not None:
            if self._step():
                self._neo.copy()
                self._neo.show()
                self._neo.sleep(self._delay_s)
                return self
        # This instruction is completed
        return None


class Sequencer():
    def __init__(self, neo_wrapper: NeoWrapper):
        self._neo_wrapper = neo_wrapper
        self._trigger = False
        self.reset()

    def reset(self) -> None:
        self._instructions = []
        self.rerun()
    
    def rerun(self):
        self._current = None
        self._pc = 0

    def parse(self, instructions: str) -> None:
        self.reset()
        for line in instructions.split(";"):
            # We don't have re.split(r"\s+", str) on CircuitPython
            lexems = [ x for x in line.strip().split(" ") if x ]
            if not lexems or lexems[0].startswith("#"):
                # Skip empty line or comment.
                continue
            verb = lexems[0].lower()
            if verb == "trigger":
                if len(lexems) > 1:
                    raise ValueError(f"Sequencer: Expected 'Trigger' with no arguments in line '{line}'")
                self._trigger = True
            elif verb == "length":
                value = -1
                if len(lexems) > 1:
                    value = int(lexems[1])
                max_len = self._neo_wrapper.max_len
                if value < 1 or value > max_len:
                    raise ValueError(f"Sequencer: Expected 'Len num_leds<1..{max_len}>' in line '{line}'")
                self._neo_wrapper.len = value
            elif verb == "brightness":
                value = -1
                if len(lexems) > 1:
                    value = float(lexems[1])
                if value < 0 or value > 1:
                    raise ValueError(f"Sequencer: Expected 'Brightness float<0..1>' in line '{line}'")
                self._neo_wrapper.brightness(value)
            elif verb == "fill":
                if (len(lexems) - 1) % 2 != 0:
                    raise ValueError("Sequencer: Expected 'Fill <rgb count> pairs' in line '%s'" % line)
                lexems.pop(0) # skip verb
                runs = [RgbCount(lexems[i*2], int(lexems[i*2+1])) for i in range(0, len(lexems) // 2)]
                inst = InstructionFill(self._neo_wrapper, 0, runs)
                self._instructions.append(inst)
            elif verb == "slowfill":
                if (len(lexems)) % 2 != 0:
                    raise ValueError("Sequencer: Expected 'SlowFill delay_s  <rgb count> pairs' in line '%s'" % line)
                lexems.pop(0) # skip verb
                delay_s = float(lexems.pop(0))
                runs = [RgbCount(lexems[i*2], int(lexems[i*2+1])) for i in range(0, len(lexems) // 2)]
                inst = InstructionFill(self._neo_wrapper, delay_s, runs)
                self._instructions.append(inst)
            elif verb == "slide":
                if len(lexems) < 3:
                    raise ValueError("Sequencer: Expected 'Slide delay_s count' in line '%s'" % line)
                inst = InstructionSlide(self._neo_wrapper, float(lexems[1]), int(lexems[2]))
                self._instructions.append(inst)
            else:
                raise ValueError("Sequencer: Unknown command '%s' in line '%s'" % (verb, line))
        print("@@ Parsed OK:", len(self._instructions), "instruction(s) found")

    def has_trigger(self) -> bool:
        t = self._trigger
        self._trigger = False
        return t

    def step(self) -> bool:
        if self._current is None:
            if self._pc >= len(self._instructions):
                return False
            self._current = self._instructions[self._pc]
            self._current = self._current.start()
            self._pc += 1
        else:
            self._current = self._current.step()
        return True

#~~
