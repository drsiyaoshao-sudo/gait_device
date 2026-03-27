# -*- coding: ascii -*-
# Renode Python peripheral -- simulation-mode UART stub for nRF52840 UARTE0.
# Python 2 (IronPython) compatible: no f-strings, no non-ASCII.
#
# Registered at sysbus 0x40002000 (size 0x1000), replacing the built-in uart0.
#
# Purpose: Renode 1.16 nRF52840 UARTE model does not re-set EVENTS_TXSTOPPED
# after processing TASKS_STARTTX.  The Zephyr nrfx UARTE driver clears
# EVENTS_TXSTOPPED before each tx_start(), then waits for it to be set again.
# Since Renode never sets it, wait_tx_ready() loops forever and all UART output
# after the first byte is lost (the first byte works because TXSTOPPED starts 1).
#
# This stub implements enough of the nRF52840 UARTE0 register map to:
#   - Always report EVENTS_TXSTOPPED and EVENTS_ENDTX as 1 (TX always ready)
#   - On TASKS_STARTTX write: read DMA bytes from machine memory and write
#     to the log file; also detect SESSION_END and write the sentinel file.
#   - Pass all other register reads/writes silently (return 0 on read).
#
# Log file path and sentinel path are communicated via well-known files:
#   ~/.gait_uart_log_path.txt    -- absolute path to uart log file
#   ~/.gait_uart_sentinel_path.txt -- absolute path to SESSION_END sentinel
#
# register map (nRF52840 UARTE0, offsets from base 0x40002000):
#   0x008  TASKS_STARTTX      (write 1 to start EasyDMA TX)
#   0x118  EVENTS_ENDTX       (always returns 1)
#   0x158  EVENTS_TXSTOPPED   (always returns 1; firmware clears = ignored)
#   0x544  TXD.PTR            (stored; used on STARTTX) — UARTE EasyDMA offset
#   0x548  TXD.MAXCNT         (stored; used on STARTTX) — UARTE EasyDMA offset
#   all others                (read returns 0; writes ignored)
#
# NOTE: TXD.PTR/MAXCNT are at 0x544/0x548, NOT 0x524/0x528.
# Confirmed via live register trace: firmware writes 0x544 then 0x548 before STARTTX.

import os
import struct

_CFG_LOG   = os.path.expanduser("~/.gait_uart_log_path.txt")
_CFG_SENT  = os.path.expanduser("~/.gait_uart_sentinel_path.txt")

def _read_cfg(path):
    try:
        f = open(path, "r")
        val = f.read().strip()
        f.close()
        return val
    except Exception:
        return ""

# Module-level globals (safe for IronPython at <100 bytes total)
if "_txd_ptr" not in globals():
    _txd_ptr = 0
if "_txd_maxcnt" not in globals():
    _txd_maxcnt = 0
if "_line_buf" not in globals():
    _line_buf = ""

TASKS_STARTTX     = 0x008
EVENTS_ENDTX      = 0x118
EVENTS_TXSTOPPED  = 0x158
# nRF52840 UARTE EasyDMA TX registers (confirmed from live register trace)
TXD_PTR           = 0x544   # TXD.PTR   (was incorrectly 0x524)
TXD_MAXCNT        = 0x548   # TXD.MAXCNT (was incorrectly 0x528)

# Offsets for registers we silently accept (no-op writes / ignored reads)
_SILENT_WRITES = set([
    0x000,  # TASKS_STARTRX
    0x004,  # TASKS_STOPRX
    0x00C,  # TASKS_STOPTX
    0x02C,  # TASKS_FLUSHRX
    0x110,  # EVENTS_ENDRX (clear)
    0x118,  # EVENTS_ENDTX (clear)
    0x120,  # EVENTS_ERROR (clear)
    0x124,  # EVENTS_RXSTARTED (clear)
    0x128,  # EVENTS_TXSTARTED (clear)
    0x130,  # EVENTS_LASTRX (clear)
    0x138,  # EVENTS_LASTTX (clear)
    0x158,  # EVENTS_TXSTOPPED (clear) — firmware clears before polling; we return 1 on read
    0x100,  # EVENTS_CTS
    0x104,  # EVENTS_NCTS
    0x108,  # EVENTS_RXDRDY
    0x200,  # SHORTS
    0x300,  # INTEN
    0x304,  # INTENSET
    0x308,  # INTENCLR
    0x4BC,  # BAUDRATE
    0x500,  # ENABLE
    0x504,  # PSEL (unused)
    0x508,  # PSEL.RTS
    0x50C,  # PSEL.TXD
    0x510,  # PSEL.CTS
    0x514,  # PSEL.RXD
    0x518,  # PSEL (unused)
    0x524,  # reserved / init-time write (observed but not TXD.PTR)
    0x528,  # reserved / init-time write
    0x534,  # RXD.PTR
    0x538,  # RXD.MAXCNT
    0x544,  # TXD.PTR  -- handled separately above
    0x548,  # TXD.MAXCNT -- handled separately above
    0x56C,  # CONFIG
])


if request.IsInit:
    _txd_ptr    = 0
    _txd_maxcnt = 0
    _line_buf   = ""
    log_path = _read_cfg(_CFG_LOG)
    if log_path:
        # Clear / create the log file
        try:
            fh = open(log_path, "w")
            fh.close()
        except Exception:
            pass
    self.NoisyLog("sim_uart_stub: initialized, log=%s" % log_path)

elif request.IsRead:
    off = request.Offset
    if off == EVENTS_TXSTOPPED or off == EVENTS_ENDTX:
        # Always report TX complete so wait_tx_ready() never blocks
        request.Value = 1
    else:
        request.Value = 0

elif request.IsWrite:
    off = request.Offset
    val = request.Value

    if off == TXD_PTR:
        _txd_ptr = val

    elif off == TXD_MAXCNT:
        _txd_maxcnt = val

    elif off == TASKS_STARTTX and val == 1:
        # Read bytes from machine DMA buffer and write to log file
        ptr   = _txd_ptr
        count = _txd_maxcnt
        if count > 0 and ptr != 0:
            chars = []
            _err_logged = False
            for i in range(count):
                try:
                    # self.GetMachine() is an inherited IPeripheral method — same
                    # API that works on Renode CPU objects in watchpoint context.
                    b = self.GetMachine().SystemBus.ReadByte(ptr + i)
                    chars.append(chr(b & 0xFF))
                except Exception as exc:
                    chars.append("?")
                    if not _err_logged:
                        _err_logged = True
                        try:
                            ef = open(os.path.expanduser("~/.gait_readbyte_err.txt"), "w")
                            ef.write("GetMachine ReadByte exc at 0x%x+%d: %s: %s\n" % (ptr, i, type(exc).__name__, str(exc)))
                            ef.close()
                        except Exception:
                            pass
            text = "".join(chars)

            log_path = _read_cfg(_CFG_LOG)
            if log_path:
                try:
                    fh = open(log_path, "a")
                    fh.write(text)
                    fh.close()
                except Exception:
                    pass

            # Detect SESSION_END across line buffer
            _line_buf = _line_buf + text
            if "SESSION_END" in _line_buf:
                sent_path = _read_cfg(_CFG_SENT)
                if sent_path:
                    try:
                        sf = open(sent_path, "w")
                        sf.write("done")
                        sf.close()
                    except Exception:
                        pass
            # Keep only last 64 chars of line buffer (enough for any log line)
            if len(_line_buf) > 64:
                _line_buf = _line_buf[-64:]

        # Fire UARTE0 IRQ (nRF52840 IRQ 2) after each TX.
        # Zephyr post-kernel uart_poll_out() waits on tx_done_sem, signalled
        # by the nrfx UARTE ISR when EVENTS_ENDTX fires.  Pulsing self.IRQ
        # here triggers that ISR so printk() unblocks in thread context.
        # The stub always returns 1 for EVENTS_ENDTX reads, so the ISR will
        # call k_sem_give(tx_done_sem) and uart_poll_out() will return.
        try:
            self.IRQ.Set()
            self.IRQ.Unset()
        except Exception:
            pass
    # All other writes are silently ignored (no action needed)
