#

import re
import time

class NeoWrapper:
    def __init__(self, target, len):
        self.data = [ (0,0,0) ] * len
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

    def __eq__(self, rhs):
        if not isinstance(rhs, self.__class__):
            return NotImplemented
        return (self._count == rhs._count
            and self._delay == rhs._delay)

    def __repr__(self):
        return f"Slide {self._delay} s x {self._count}"


class InstructionFill(Instruction):
    def __init__(self, neo: NeoWrapper, delay: float, runs: list[RgbCount]):
        super().__init__(neo)
        self._delay = delay
        self._runs = runs

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
        if self._delay <= 0:
            # Instant fill
            run_index = 0
            curr_rgb = None
            curr_count = 0
            for i in range(0, self._neo.len):
                if curr_rgb is None:
                    run_curr = self._runs[run_index]
                    curr_rgb = run_curr.rgb.asTuple()
                    curr_count = run_curr.count
                    run_index += 1
                    if run_index == len(self._runs):
                        run_index = 0
                self._neo.data[i] = curr_rgb
                curr_count -= 1
                if curr_count <= 0:
                    curr_rgb = None
            self._neo.copy()
            self._neo.show()
        return None

    def step(self) -> Instruction:
        return None


class Sequencer():
    def __init__(self, neo_wrapper: NeoWrapper):
        self._neo_wrapper = neo_wrapper
        self.reset()

    def reset(self) -> None:
        self._instructions = []
        self._current = None
        self._pc = 0

    def parse(self, instructions: str) -> None:
        self.reset()
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

    def step(self) -> None:
        if self._current is None:
            if self._pc >= len(self._instructions):
                return
            self._pc += 1
            self._current = self._instructions[self._pc]
            self._current = self._current.start()
        else:
            self._current = self._current.step()

#~~
