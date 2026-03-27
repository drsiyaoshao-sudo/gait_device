"""
Layer 2-6 orchestration bridge — Renode pipeline.

Drives the full embedded simulation path:

    Walker samples (float32)
        │  imu_model.quantize_to_file()
        ▼
    /tmp/gait_imu_fifo.bin          ← lsm6ds3_stub.py reads this at init
        │  Renode process (firmware.elf on nRF52840 + LSM6DS3 stub)
        ▼
    /tmp/gait_uart.log              ← firmware emits STEP/SNAPSHOT/SESSION_END
        │  signal_analysis.parse_uart_log()
        ▼
    (steps, snapshots, session_ends)

Public API
----------
    RenoneBridge(elf_path, repl_path, resc_path)
    bridge.run(samples) -> (steps, snapshots, session_ends)

    detect_renode() -> str | None          # path to renode binary or None
    detect_firmware() -> str | None        # path to firmware.elf or None
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import numpy as np

from imu_model import quantize_to_file
from signal_analysis import parse_uart_log, StepEvent, SnapshotEvent, SessionEndEvent

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Sim variant ELF — ninja-produced zephyr.elf has app/libapp.a correctly linked.
# PlatformIO's own firmware.elf omits libapp.a (a known PlatformIO-Zephyr bug
# where the app target is excluded from SCons link and native compilation is skipped).
# The two-step build (pio run → ninja zephyr.elf) produces the correct binary.
_DEFAULT_ELF  = _PROJECT_ROOT / ".pio/build/xiaoble_sense_sim/zephyr/zephyr.elf"
_PIO_ELF      = _PROJECT_ROOT / ".pio/build/xiaoble_sense_sim/firmware.elf"   # fallback only

# Hardware ELF (CONFIG_GAIT_RENODE_SIM not set) — kept for reference
_HARDWARE_ELF = _PROJECT_ROOT / ".pio/build/xiaoble_sense/firmware.elf"

_NINJA_BIN = Path("/Users/siyaoshao/.platformio/packages/tool-ninja/ninja")

_DEFAULT_REPL = _PROJECT_ROOT / "renode/gait_nrf52840.repl"
_DEFAULT_RESC = _PROJECT_ROOT / "renode/gait_device.resc"

# /tmp is sandboxed on macOS for .app bundles — Renode can't write there.
# Use the user's home directory for the UART log (Renode has home-dir access).
# IMU sim file: float32 format (not int16), written by Python → readable by Python.
_IMU_BIN_PATH  = Path("/tmp/gait_imu_fifo.bin")   # legacy / unused by sim path
_IMU_SIM_PATH  = Path("/tmp/gait_imu_sim.f32")    # float32, used by sim_imu_stub.py
_UART_LOG_PATH = Path.home() / "gait_uart.log"

# Renode telnet monitor port (Renode's default)
_TELNET_HOST = "127.0.0.1"
_TELNET_PORT = 1234

# Timeouts (seconds)
_BOOT_TIMEOUT_S      = 10.0   # wait for Renode to start and firmware to boot
_SESSION_TIMEOUT_S   = 120.0  # max time to wait for SESSION_END in UART log
_POLL_INTERVAL_S     = 0.2    # how often to check UART log for completion


# ─────────────────────────────────────────────────────────────────────────────
# Auto-detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_renode() -> Optional[str]:
    """Return path to the renode binary if found on PATH, else None."""
    return shutil.which("renode")


def detect_firmware(elf_path: Optional[str | Path] = None) -> Optional[str]:
    """Return path to the sim firmware ELF if it exists, else None.

    Prefers the ninja-produced ``zephyr/zephyr.elf`` which correctly links
    ``app/libapp.a``.  Falls back to PlatformIO's ``firmware.elf`` (which
    lacks app code due to a PlatformIO-Zephyr build system mismatch) only as
    a last resort so callers can detect that a build is needed.
    """
    candidates = [
        Path(elf_path) if elf_path else None,
        _DEFAULT_ELF,       # ninja zephyr.elf — preferred
        _PIO_ELF,           # PlatformIO firmware.elf — fallback (may lack app code)
        _PROJECT_ROOT / ".pio/build/xiaoble_sense/firmware.elf",
    ]
    for p in candidates:
        if p and p.exists():
            return str(p)
    return None


def build_sim_firmware() -> str:
    """Build the sim firmware ELF via PlatformIO + ninja and return its path.

    Two-step process:
      1. ``pio run -e xiaoble_sense_sim`` — configures CMake, compiles Zephyr
         framework libraries via PlatformIO SCons, writes build.ninja.
      2. ``ninja zephyr/zephyr.elf``     — links the final ELF including
         app/libapp.a (which PlatformIO's own link step omits).

    Raises RuntimeError on build failure.
    """
    build_dir = _PROJECT_ROOT / ".pio/build/xiaoble_sense_sim"

    # Step 1: PlatformIO configure + framework compile
    r = subprocess.run(
        ["pio", "run", "-e", "xiaoble_sense_sim"],
        cwd=str(_PROJECT_ROOT),
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"PlatformIO build failed (step 1):\n{r.stdout[-2000:]}\n{r.stderr[-1000:]}"
        )

    # Step 2: ninja final link (produces zephyr/zephyr.elf with app code)
    ninja_bin = str(_NINJA_BIN) if _NINJA_BIN.exists() else "ninja"
    r2 = subprocess.run(
        [ninja_bin, "zephyr/zephyr.elf"],
        cwd=str(build_dir),
        capture_output=True, text=True,
    )
    if r2.returncode != 0:
        raise RuntimeError(
            f"ninja build failed (step 2):\n{r2.stdout[-2000:]}\n{r2.stderr[-1000:]}"
        )

    elf = build_dir / "zephyr/zephyr.elf"
    if not elf.exists():
        raise RuntimeError(f"Expected ELF not found after build: {elf}")
    return str(elf)


def is_available(
    elf_path: Optional[str | Path] = None,
) -> bool:
    """Return True if both Renode and the firmware ELF are available."""
    return bool(detect_renode() and detect_firmware(elf_path))


# ─────────────────────────────────────────────────────────────────────────────
# Telnet monitor client (minimal — send commands, read responses)
# ─────────────────────────────────────────────────────────────────────────────

class _MonitorClient:
    """Minimal telnet client for Renode's interactive monitor."""

    def __init__(self, host: str = _TELNET_HOST, port: int = _TELNET_PORT):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(5.0)
        self._sock.connect((host, port))
        self._buf = b""

    def _recv_until(self, marker: bytes, timeout: float = 5.0) -> str:
        deadline = time.monotonic() + timeout
        while True:
            idx = self._buf.find(marker)
            if idx >= 0:
                out = self._buf[:idx].decode("utf-8", errors="replace")
                self._buf = self._buf[idx + len(marker):]
                return out
            if time.monotonic() > deadline:
                raise TimeoutError(f"Renode monitor: timed out waiting for {marker!r}")
            try:
                chunk = self._sock.recv(4096)
                if chunk:
                    self._buf += chunk
            except socket.timeout:
                pass

    def send(self, cmd: str, timeout: float = 30.0) -> str:
        """Send a monitor command and return the response up to the next prompt.

        Renode's prompt is ``(<name>) `` — ``(monitor) `` at top level,
        ``(machine_name) `` when a machine is selected.  Search for the
        common suffix ``") "`` (close-paren space) so the method works
        regardless of which machine context is active.

        Default timeout is 30s to accommodate slow operations like ELF loading
        and emulation RunFor calls that advance significant simulated time.
        """
        self._sock.sendall((cmd.strip() + "\n").encode())
        return self._recv_until(b") \x1b[0m", timeout=timeout)

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Main bridge class
# ─────────────────────────────────────────────────────────────────────────────

class RenoneBridge:
    """
    Orchestrates a single Renode simulation run.

    Parameters
    ----------
    elf_path : str | Path
        Path to the firmware ELF to run (must exist).
    repl_path : str | Path
        Path to the Renode platform description file.
    resc_path : str | Path
        Path to the Renode scenario (.resc) file.
    imu_bin : Path
        Where to write the quantized IMU binary (read by lsm6ds3_stub.py).
    uart_log : Path
        Where Renode writes UART output (tailed by the bridge).
    telnet_port : int
        Renode monitor telnet port.
    stationary_prefix_samples : int
        Number of stationary (1g on az) samples prepended before the walk
        sequence so the firmware's calibration window sees quiet data.
    """

    def __init__(
        self,
        elf_path:  str | Path,
        repl_path: str | Path = _DEFAULT_REPL,
        resc_path: str | Path = _DEFAULT_RESC,
        imu_sim:   Path       = _IMU_SIM_PATH,
        uart_log:  Path       = _UART_LOG_PATH,
        telnet_port: int      = _TELNET_PORT,
        stationary_prefix_samples: int = 450,  # ≥ CAL_SAMPLES(400) + margin
    ):
        self.elf_path   = Path(elf_path)
        self.repl_path  = Path(repl_path)
        self.resc_path  = Path(resc_path)
        self.imu_sim    = imu_sim
        self.uart_log   = uart_log
        self.telnet_port = telnet_port
        self.stationary_prefix_n = stationary_prefix_samples

        self._proc:     Optional[subprocess.Popen] = None
        self._monitor:  Optional[_MonitorClient]   = None
        self._n_samples: int = 0   # set by _prepare_imu_file
        self._tmp_repl:  Optional[str] = None       # temp REPL 1 (base + imu stub)
        self._tmp_repl2: Optional[str] = None       # temp REPL 2 (uart stub)
        self._renode_log_path: Optional[Path] = None  # Renode stdout/stderr log
        self._session_end_sentinel: Optional[Path] = None  # written by sim_uart_stub
        self._sim_failed: bool = False              # set True on exception for log retention

    # ── public API ──────────────────────────────────────────────────────────

    def run(
        self,
        samples: np.ndarray,
    ) -> tuple[list[StepEvent], list[SnapshotEvent], list[SessionEndEvent]]:
        """
        Run a full simulation for the given IMU samples.

        Parameters
        ----------
        samples : np.ndarray (N, 6)
            Physical-unit float32 [ax ay az gx gy gz] from walker_model.

        Returns
        -------
        (steps, snapshots, session_ends)  — same types as gait_algorithm.run()
        """
        self._sim_failed = False
        try:
            self._prepare_imu_file(samples)
            self._start_renode()
            self._configure_renode()
            self._wait_for_session_end()
        except Exception:
            self._sim_failed = True
            raise
        finally:
            self._stop_renode()

        return self._parse_uart_log()

    # ── internal helpers ─────────────────────────────────────────────────────

    def _prepare_imu_file(self, samples: np.ndarray):
        """Prepend stationary prefix and write float32 sim file."""
        G = 9.81
        n_pre = self.stationary_prefix_n
        # Stationary: az = +1g, all others = 0.  We need ≥ 400 samples for the
        # calibration window; the default prefix is 450 (≥ CAL_SAMPLES=400).
        stationary = np.zeros((n_pre, 6), dtype=np.float32)
        stationary[:, 2] = G            # az = +9.81 m/s²

        full = np.vstack([stationary, samples.astype(np.float32)])
        self._n_samples = len(full)

        # Write float32 binary file for sim_imu_stub.py
        # Format: N × 24 bytes = N × [ax ay az gx gy gz] float32 LE
        full.astype(np.float32).tofile(str(self.imu_sim))

        # Remove previous UART log so Renode creates it fresh
        self.uart_log.unlink(missing_ok=True)

        # Write log/sentinel paths to config files for sim_uart_stub.py to read.
        # IronPython cannot receive dynamic arguments; config files bridge the gap.
        _LOG_CFG  = Path.home() / ".gait_uart_log_path.txt"
        _SENT_CFG = Path.home() / ".gait_uart_sentinel_path.txt"
        _LOG_CFG.write_text(str(self.uart_log))
        sentinel = str(self.uart_log) + ".done"
        _SENT_CFG.write_text(sentinel)

    def _start_renode(self):
        """Launch Renode in headless mode and wait for the monitor port."""
        renode_bin = detect_renode()
        if not renode_bin:
            raise RuntimeError("renode binary not found on PATH")

        cmd = [
            renode_bin,
            "--disable-xwt",
            "--port", str(self.telnet_port),
        ]
        # Redirect stdout/stderr to files, not PIPE — PIPE buffers fill up
        # and block Renode from writing log output, causing deadlock during RunFor.
        _renode_log = Path(tempfile.mktemp(suffix="_renode.log"))
        self._renode_log_path = _renode_log
        self._proc = subprocess.Popen(
            cmd,
            stdout=open(str(_renode_log), "w"),
            stderr=subprocess.STDOUT,
            cwd=str(_PROJECT_ROOT),
        )

        # Wait for Renode's telnet monitor to become available
        deadline = time.monotonic() + _BOOT_TIMEOUT_S
        while time.monotonic() < deadline:
            try:
                self._monitor = _MonitorClient(
                    _TELNET_HOST, self.telnet_port
                )
                # Drain the banner — wait for the first Renode prompt.
                # Prompt format: \x1b[<color>m(<name>) \x1b[0m
                self._monitor._recv_until(b") \x1b[0m", timeout=5.0)
                return
            except (ConnectionRefusedError, OSError, TimeoutError):
                time.sleep(0.3)

        # Read Renode log file for diagnosis
        log_snippet = ""
        if self._renode_log_path and self._renode_log_path.exists():
            try:
                log_snippet = f"\nRenode log: {self._renode_log_path.read_text(errors='replace')[-500:]}"
            except Exception:
                pass
        raise RuntimeError(
            f"Renode monitor did not open on port {self.telnet_port} "
            f"within {_BOOT_TIMEOUT_S}s{log_snippet}"
        )

    def _configure_renode(self):
        """Set up the machine and execute firmware directly via monitor commands.

        Python peripheral strategy (Strike 3 — self.GetMachine() DMA read):
          REPL 1: nrf52840.repl base + sim_imu stub (no uart0 override)
          Monitor: sysbus Unregister uart0  (remove built-in UARTE0 model)
          REPL 2: sim_uart_stub.py at 0x40002000 — handles TXSTOPPED fix AND
            DMA byte capture via self.GetMachine().SystemBus.ReadByte()
            (self.GetMachine() is inherited IPeripheral method, works on CPU objects
            in Renode watchpoint context — testing if it also works in PythonPeripheral)
        """
        mon = self._monitor

        imu_stub_abs  = str((_PROJECT_ROOT / "renode/sim_imu_stub.py").resolve())
        uart_stub_abs = str((_PROJECT_ROOT / "renode/sim_uart_stub.py").resolve())

        # ── REPL 1: base platform + IMU stub ──────────────────────────────────
        repl1_content = (
            'using "platforms/cpus/nrf52840.repl"\n\n'
            'sim_imu: Python.PythonPeripheral @ sysbus 0x400B0000\n'
            '    size: 0x100\n'
            f'    filename: "{imu_stub_abs}"\n'
            '    initable: true\n'
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".repl", delete=False) as tmp:
            tmp.write(repl1_content)
            self._tmp_repl = tmp.name

        # ── REPL 2: UART Python stub ───────────────────────────────────────────
        # Note: Python.PythonPeripheral has no GPIO property (Renode 1.16), so
        # -> nvic@2 is NOT used here.  Instead a sysbus AddWatchpointHook on
        # TASKS_STARTTX (0x40002008) writes to NVIC_ISPR0 (0xE000E200) bit 2
        # to pending-trigger IRQ 2 (UARTE0) after each TX, which is installed
        # in _configure_renode() below after LoadELF.
        repl2_content = (
            'sim_uart: Python.PythonPeripheral @ sysbus <0x40002000, +0x1000>\n'
            '    size: 0x1000\n'
            f'    filename: "{uart_stub_abs}"\n'
            '    initable: true\n'
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".repl", delete=False) as tmp:
            tmp.write(repl2_content)
            self._tmp_repl2 = tmp.name

        # ── Machine setup ──────────────────────────────────────────────────────
        r = mon.send('mach create "gait_device"')
        print(f"[Renode] mach create          : {r.strip()!r}")

        r = mon.send(f"machine LoadPlatformDescription @{self._tmp_repl}")
        print(f"[Renode] LoadPlatformDesc (1) : {r.strip()!r}")
        if "error" in r.lower() or "exception" in r.lower():
            raise RuntimeError(f"REPL 1 load failed: {r.strip()}")

        r = mon.send("sysbus Unregister uart0")
        print(f"[Renode] Unregister uart0     : {r.strip()!r}")

        r = mon.send(f"machine LoadPlatformDescription @{self._tmp_repl2}")
        print(f"[Renode] LoadPlatformDesc (2) : {r.strip()!r}")
        if "error" in r.lower() or "exception" in r.lower():
            raise RuntimeError(f"REPL 2 (uart stub) load failed: {r.strip()}")

        r = mon.send(f"sysbus LoadELF @{self.elf_path}", timeout=60.0)
        print(f"[Renode] LoadELF              : {r.strip()!r}")
        if "error" in r.lower() or "exception" in r.lower():
            raise RuntimeError(f"ELF load failed: {r.strip()}")

        # UART interrupt fix: fire UARTE0 IRQ (IRQ 2) on every TASKS_STARTTX write.
        # Python.PythonPeripheral has no GPIO (cannot use -> nvic@2 in REPL).
        # Watchpoint on TASKS_STARTTX (0x40002008) writes to NVIC_ISPR0 bit 2
        # (0xE000E200 = 0x4) to set IRQ 2 pending. The NVIC then fires IRQ 2
        # (UARTE0 ISR), which calls k_sem_give(tx_done_sem) so Zephyr post-kernel
        # uart_poll_out() unblocks.  Our stub returns 1 for EVENTS_ENDTX reads so
        # the ISR correctly signals TX completion.
        # Width=4 (32-bit), access=2 (Write).
        wp_hook = (
            "self.GetMachine().SystemBus.WriteDoubleWord(0xE000E200, 4)"
        )
        r = mon.send(f'sysbus AddWatchpointHook 0x40002008 4 2 "{wp_hook}"')
        print(f"[Renode] WatchpointHook UART  : {r.strip()!r}")

        # Sentinel: sim_uart_stub.py writes this when SESSION_END is detected.
        sentinel = str(self.uart_log) + ".done"
        self._session_end_sentinel = Path(sentinel)
        self._session_end_sentinel.unlink(missing_ok=True)

        # Boot the firmware (1.5 s simulated) then a short settling period.
        r = mon.send('emulation RunFor "1.5"', timeout=60.0)
        print(f"[Renode] RunFor 1.5s (boot)   : {r.strip()!r}")
        r = mon.send('emulation RunFor "0.1"', timeout=30.0)
        print(f"[Renode] RunFor 0.1s (settle) : {r.strip()!r}")

    def _wait_for_session_end(self):
        """Advance simulated time until SESSION_END appears in the UART log.

        The firmware auto-starts the session and auto-stops when the IMU stub
        runs out of samples. sim_uart_stub.py writes a sentinel file the instant
        SESSION_END appears in UART output — we poll that file (real-time).
        """
        mon = self._monitor

        # Budget: consume all samples + 2s margin + 1s auto-stop pipeline flush.
        odr = 208.0
        walk_time_s = self._n_samples / odr
        run_budget_s = walk_time_s + 3.0   # auto-stop adds ~0.5s; +3s gives margin
        elapsed_s = 0.0
        chunk_s = 0.5

        sentinel = self._session_end_sentinel

        deadline = time.monotonic() + _SESSION_TIMEOUT_S
        while time.monotonic() < deadline:
            mon.send(f"emulation RunFor \"{chunk_s}\"")
            elapsed_s += chunk_s
            if sentinel and sentinel.exists():
                return
            time.sleep(_POLL_INTERVAL_S)
            if elapsed_s > run_budget_s + 5.0:
                break   # give up waiting

        raise TimeoutError(
            f"SESSION_END not seen after {elapsed_s:.1f}s simulated "
            f"({self._n_samples} samples, {walk_time_s:.1f}s walk)"
        )

    def _stop_renode(self):
        """Cleanly shut down the Renode process."""
        if self._monitor:
            try:
                self._monitor.send("quit")
            except Exception:
                pass
            self._monitor.close()
            self._monitor = None

        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

        for attr in ("_tmp_repl", "_tmp_repl2"):
            p = getattr(self, attr, None)
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    pass
                setattr(self, attr, None)

        if self._session_end_sentinel:
            try:
                self._session_end_sentinel.unlink(missing_ok=True)
            except Exception:
                pass
            self._session_end_sentinel = None

        if self._renode_log_path:
            if self._sim_failed and self._renode_log_path.exists():
                # Print tail of Renode log so the failure is diagnosable
                try:
                    tail = self._renode_log_path.read_text(errors="replace")[-2000:]
                    print(f"\n[Renode log tail]\n{tail}\n[/Renode log]")
                except Exception:
                    pass
            try:
                self._renode_log_path.unlink(missing_ok=True)
            except Exception:
                pass
            self._renode_log_path = None


    def _parse_uart_log(
        self,
    ) -> tuple[list[StepEvent], list[SnapshotEvent], list[SessionEndEvent]]:
        """Read the UART log file and parse it with signal_analysis."""
        text = self.uart_log.read_text(encoding="utf-8", errors="replace")
        return parse_uart_log(text)
