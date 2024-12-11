# Lights Test
# 2024 (c) ralfoide at gmail
# License: MIT

import sequencer

class ScriptExec:
    def __init__(self, seq: sequencer.Sequencer, blink_f):
        self._seq = seq
        self._script = ""
        self._trigger = False
        self._blink_f = blink_f

    def loop(self):
        if self._trigger:
            self._trigger = False
            self.exec()

    def newScript(self, script):
        if self._script != script:
            self._script = script
            self._onChanged()

    def _onChanged(self):
        self._seq.parse(self._script)

    def trigger(self):
        self._trigger = True

    def exec(self):
        if self._script:
            print("@@ Exec script", self._script)
            while self._seq.step():
                self._blink_f()
            self._seq.rerun()


class InitScriptExec(ScriptExec):
    def __init__(self, seq: sequencer.Sequencer, blink_f):
        super().__init__(seq, blink_f)
        self.trigger()

    def _onChanged(self):
        super()._onChanged()
        self.trigger()

    def loadFromNVM(self):
        # TBD load from NVM and call newScript(script)
        pass


class EventScriptExec(ScriptExec):
    def __init__(self, seq: sequencer.Sequencer, blink_f):
        super().__init__(seq, blink_f)
