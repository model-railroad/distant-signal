# Lights Test
# 2024 (c) ralfoide at gmail
# License: MIT

import microcontroller
import sequencer
import struct

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
        self._nvm_script = None

    def _onChanged(self):
        super()._onChanged()
        self.trigger()
        self.saveToNVM()

    def saveToNVM(self):
        if self._script == self._nvm_script:
            return
        try:
            # Header format: 8-byte header with
            # "AMBI" prefix + CRC head + CRC script + 2 bytes str length
            # followed by the script string in UTF-8.
            #              ppppCCLL
            b = bytearray("AMBI0011".encode())
            s = self._script.encode()

            # Fixed header
            struct.pack_into("!H", b, 6, len(s))
            crc_fix = 0
            for i in b:
                crc_fix = crc_fix ^ i
            b[4] = crc_fix

            # Variable payload
            b.extend(s)
            crc_var = 0
            for i in s:
                crc_var = crc_var ^ i
            b[5] = crc_var

            print("@@ Write NVM: ", b.hex())
            microcontroller.nvm[0 : len(b)] = b

            self._nvm_script = self._script
        except Exception as e:
            print("@@ Write NVM failed: ", e)

    def loadFromNVM(self):
        try:
            fixed = microcontroller.nvm[0 : 8]
            crc_fix = fixed[4]
            crc_var = fixed[5]
            fixed[4] = 0
            fixed[5] = 0

            crc_f = 0
            for i in fixed:
                crc_f = crc_f ^ i
            if fixed[0:4].decode() != "AMBI" or crc_fix != crc_f:
                print("@@ Read NVM: invalid Header/CRC", crc_fix, "in", fixed.hex())
                return

            slen = struct.unpack_from("!H", fixed, 6)[0]
            s = microcontroller.nvm[8 : 8 + slen]
            crc_s = 0
            for i in s:
                crc_s = crc_s ^ i

            if crc_s != crc_var:
                print("@@ Read NVM: invalid Script CRC", crc_s, "in", fixed.hex(), "+", s.hex())
                return

            self._nvm_script = s.decode()
            print("@@ Read NVM:", self._nvm_script)
            self.newScript(self._nvm_script)

        except Exception as e:
            print("@@ Read NVM failed: ", e)

class EventScriptExec(ScriptExec):
    def __init__(self, seq: sequencer.Sequencer, blink_f):
        super().__init__(seq, blink_f)
