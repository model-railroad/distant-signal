# LED NeoPixel Sequencer
# 2024 (c) ralfoide at gmail
# License: MIT
#
# Target Platform: CircuitPython 9.x on AdaFruit QT PY ESP32-S2
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
    def __init__(self, target, len):
        self.data = [ target[i] for i in range(0, len) ]
        self.len = len
        self._target = target

    def copy(self):
        self._target[:] = self.data

    def show(self):
        self._target.show()

    def sleep(self, seconds: float):
        time.sleep(seconds)


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
    def __init__(self, neo: NeoWrapper, delay: float, count: int):
        super().__init__(neo)
        self._delay = delay
        self._count = count
        self._data = None

    def __eq__(self, rhs):
        if not isinstance(rhs, self.__class__):
            return NotImplemented
        return (self._count == rhs._count
            and self._delay == rhs._delay)

    def __repr__(self):
        return f"Slide {self._delay} s x {self._count}"

    def start(self) -> Instruction:
        self._data = self._count
        return self.step()

    def step(self) -> Instruction:
        if self._data is None:
            return None
        count = self._data
        nl = self._neo.len
        delay = self._delay
        if delay >= 0:
            first = self._neo.data[0]
            self._neo.data[0 : nl-1] = self._neo.data[1 : nl]
            self._neo.data[-1] = first
        else:
            delay = -delay
            last = self._neo.data[-1]
            self._neo.data[1 : nl] = self._neo.data[0 : nl-1]
            self._neo.data[0] = last
        self._neo.copy()
        self._neo.show()
        self._neo.sleep(delay)
        count -= 1
        if count > 0:
            self._data = count
            return self
        # This instruction is completed
        self._data = None
        return None


class InstructionFill(Instruction):
    def __init__(self, neo: NeoWrapper, delay: float, runs: list[RgbCount]):
        super().__init__(neo)
        self._delay = delay
        self._runs = runs
        self._data = None

    def __eq__(self, rhs):
        if not isinstance(rhs, self.__class__):
            return NotImplemented
        # runs_ok = all(x == y for x, y in zip(self._runs, rhs._runs))
        runs_ok = (self._runs == rhs._runs)
        return (runs_ok
            and self._delay == rhs._delay)

    def __repr__(self):
        return f"Fill {self._delay} s x {self._runs}"

    def start(self) -> Instruction:
        # Instant fill
        self._data = (0, 0, 0, None)
        if self._delay == 0:
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
                self._neo.sleep(self._delay)
                return self
        # This instruction is completed
        return None


class Sequencer():
    def __init__(self, neo_wrapper: NeoWrapper):
        self._neo_wrapper = neo_wrapper
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
            if verb == "fill":
                if (len(lexems) - 1) % 2 != 0:
                    raise ValueError("Sequencer: Expected 'Fill <rgb count> pairs' in line '%s'" % line)
                lexems.pop(0) # skip verb
                runs = [RgbCount(lexems[i*2], int(lexems[i*2+1])) for i in range(0, len(lexems) // 2)]
                inst = InstructionFill(self._neo_wrapper, 0, runs)
                self._instructions.append(inst)
            elif verb == "slowfill":
                if (len(lexems)) % 2 != 0:
                    raise ValueError("Sequencer: Expected 'SlowFill delay  <rgb count> pairs' in line '%s'" % line)
                lexems.pop(0) # skip verb
                delay = float(lexems.pop(0))
                runs = [RgbCount(lexems[i*2], int(lexems[i*2+1])) for i in range(0, len(lexems) // 2)]
                inst = InstructionFill(self._neo_wrapper, delay, runs)
                self._instructions.append(inst)
            elif verb == "slide":
                if len(lexems) < 3:
                    raise ValueError("Sequencer: Expected 'Slide delay count' in line '%s'" % line)
                inst = InstructionSlide(self._neo_wrapper, float(lexems[1]), int(lexems[2]))
                self._instructions.append(inst)
            else:
                raise ValueError("Sequencer: Unknown command '%s' in line '%s'" % (verb, line))

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
