#

import re
import time

class Rgb():
    def __init__(self, rgb: str):
        if len(rgb) != 6 and len(rgb) != 7:
            raise ValueError("Sequencer: RGB expected in hex format [#?]RRGGBB but was '%s'" % rgb)
        if rgb.startswith("#"):
            rgb = rgb[1:]
        self.r = int(rgb[0:2], 16)
        self.g = int(rgb[2:4], 16)
        self.b = int(rgb[4:6], 16)

    def __eq__(self, rhs):
        if not isinstance(rhs, self.__class__):
            return False
        return (self.r == rhs.r
            and self.g == rhs.g
            and self.b == rhs.b)

    def __repr__(self):
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

class RgbCount():
    def __init__(self, rgb: str, count: int):
        self.rgb = Rgb(rgb)
        self.count = count

    def __eq__(self, rhs):
        if not isinstance(rhs, self.__class__):
            return False
        return (self.rgb == rhs.rgb
            and self.count == rhs.count)
    
    def __repr__(self):
        return f"<{self.rgb},{self.count}>"

class Instruction():
    def __init__(self):
        pass

class InstructionSlide(Instruction):
    def __init__(self, delay: float, count: int):
        self._delay = delay
        self._count = count
    
    def __eq__(self, rhs):
        if not isinstance(rhs, self.__class__):
            return False
        return (self._count == rhs._count 
            and self._delay == rhs._delay)

    def __repr__(self):
        return f"Slide {self._delay} s x {self._count}"

class InstructionFill(Instruction):
    def __init__(self, delay: float, runs: list[RgbCount]):
        self._delay = delay
        self._runs = runs
    
    def __eq__(self, rhs):
        if not isinstance(rhs, self.__class__):
            return False
        runs_ok = all(x == y for x, y in zip(self._runs, rhs._runs))
        if not runs_ok:
            raise ValueError("runs not ok: %s vs %s" % (self._runs, rhs._runs) )
        return (runs_ok 
            and self._delay == rhs._delay)
    
    def __repr__(self):
        return f"Fill {self._delay} s x {self._runs}"

class Sequencer():
    def __init__(self,
                sleep_f = time.sleep):
        # Function overrides for unit tests
        self._sleep_f = sleep_f
        self._instructions = []
        self._pc = 0

    def parse(self, instructions: str) -> None:
        self._instructions = []
        self._pc = 0
        for line in instructions.split(";"):
            lexems = re.split(r"\s+", line.strip())
            if not lexems or lexems[0].startswith("#"):
                # Skip empty line or comment.
                continue
            verb = lexems[0].lower()
            if verb == "fill":
                if (len(lexems) - 1) % 2 != 0:
                    raise ValueError("Sequencer: Expected 'Fill <rgb count> pairs' in line '%s'" % line)
                lexems.pop(0) # skip verb
                runs = [RgbCount(lexems[i*2], lexems[i*2+1]) for i in range(0, len(lexems) // 2)]
                inst = InstructionFill(0, runs)
                self._instructions.append(inst)
            elif verb == "slowfill":
                if (len(lexems)) % 2 != 0:
                    raise ValueError("Sequencer: Expected 'SlowFill delay  <rgb count> pairs' in line '%s'" % line)
                lexems.pop(0) # skip verb
                delay = float(lexems.pop(0))
                runs = [RgbCount(lexems[i*2], lexems[i*2+1]) for i in range(0, len(lexems) // 2)]
                inst = InstructionFill(delay, runs)
                self._instructions.append(inst)
            elif verb == "slide":
                if len(lexems) < 3:
                    raise ValueError("Sequencer: Expected 'Slide delay count' in line '%s'" % line)
                inst = InstructionSlide(float(lexems[1]), int(lexems[2]))
                self._instructions.append(inst)
            else:
                raise ValueError("Sequencer: Unknown command '%s' in line '%s'" % (verb, line))
    
    def step(self) -> None:
        pass

#~~
