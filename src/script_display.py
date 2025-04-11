# Distant Signal
# 2025 (c) ralfoide at gmail
# License: MIT

import adafruit_hashlib
import microcontroller
import struct

from script_parser import ScriptParser


class ScriptDisplay:
    def __init__(self, parser: ScriptParser, display):
        self._parser = parser
        self._display = display
        self._script_hash = None
        self._active_state = ""
        self._active_blocks = {}

    def newScript(self, script: str, saveToNVM:bool) -> bool:
        # Return true if the script has changed.
        script_hash = self._scriptHash(script)
        if script_hash != self._script_hash:
            self._parser.parseJson(script)
            if self._onChanged(script, saveToNVM):
                self._script_hash = script_hash
                return True
        return False

    def loadFromNVM(self) -> bool:
        # This calls newScript() on success
        return self._loadFromNVM()

    def setState(self, state:str) -> None:
        if self._active_state != state:
            self._active_state = state
            self._update()

    def setBlockState(self, block:str, active:bool) -> None:
        if self._active_blocks.get(block, False) != active:
            self._active_blocks[block] = active
            self._update()

    def _onChanged(self, script: str, saveToNVM:bool) -> None:
        saved = True
        if saveToNVM:
            saved = self._saveToNVM(script)
        self._update()
        return saved

    def _update(self) -> None:
        active_blocks = [ k for k,v in self._active_blocks.items() if v ]
        self._parser.display(self._display, self._active_state, active_blocks)

    def _scriptHash(self, script) -> str:
        m = adafruit_hashlib.sha1()
        m.update(script.encode())
        return m.hexdigest()

    def _saveToNVM(self, script) -> bool:
        try:
            # Header format: 8-byte header with
            # "AMBI" prefix + CRC head + CRC script + 2 bytes str length
            # followed by the script string in UTF-8.
            #              ppppCCLL
            b = bytearray("AMBI0011".encode())
            s = script.encode()

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

            print("@@ Write NVM:", len(b), "bytes")
            microcontroller.nvm[0 : len(b)] = b
            return True
        except Exception as e:
            print("@@ Write NVM failed: ", e)
            return False

    def _loadFromNVM(self) -> bool:
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
                return False

            slen = struct.unpack_from("!H", fixed, 6)[0]
            s = microcontroller.nvm[8 : 8 + slen]
            crc_s = 0
            for i in s:
                crc_s = crc_s ^ i

            if crc_s != crc_var:
                print("@@ Read NVM: invalid Script CRC", crc_s, "in", fixed.hex(), "+", s.hex())
                return False

            script = s.decode()
            print("@@ Read NVM:", len(script), "characters")
            self.newScript(script, saveToNVM=False)
            return True
        except Exception as e:
            print("@@ Read NVM failed: ", e)
            return False
