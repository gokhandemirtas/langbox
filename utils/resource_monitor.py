"""Background thread that logs VRAM and system memory usage every N seconds."""

import os
import threading

import psutil
from loguru import logger
from pynvml import nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo, nvmlInit


def _monitor_loop(interval: float, stop_event: threading.Event):
  """Periodically log GPU VRAM and system RAM usage."""
  nvmlInit()
  gpu_handle = nvmlDeviceGetHandleByIndex(0)
  process = psutil.Process(os.getpid())

  while not stop_event.wait(interval):
    # GPU VRAM
    gpu_info = nvmlDeviceGetMemoryInfo(gpu_handle)
    gpu_used = gpu_info.used / 1024**2
    gpu_total = gpu_info.total / 1024**2

    # System RAM (process-level)
    mem_info = process.memory_info()
    rss = mem_info.rss / 1024**2

    # System RAM (overall)
    sys_mem = psutil.virtual_memory()
    sys_used = sys_mem.used / 1024**2
    sys_total = sys_mem.total / 1024**2

    logger.info(
      f"[monitor] VRAM: {gpu_used:.0f}/{gpu_total:.0f}MB | "
      f"RAM (process): {rss:.0f}MB | "
      f"RAM (system): {sys_used:.0f}/{sys_total:.0f}MB"
    )


_stop_event: threading.Event | None = None
_thread: threading.Thread | None = None


def start_monitor(interval: float = 1.0):
  """Start the background resource monitor.

  Args:
      interval: Seconds between reports (default: 1.0)
  """
  global _stop_event, _thread
  if _thread is not None and _thread.is_alive():
    logger.warning("Resource monitor already running")
    return

  _stop_event = threading.Event()
  _thread = threading.Thread(
    target=_monitor_loop,
    args=(interval, _stop_event),
    daemon=True,
    name="resource-monitor",
  )
  _thread.start()
  logger.info(f"Resource monitor started (interval={interval}s)")


def stop_monitor():
  """Stop the background resource monitor."""
  global _stop_event, _thread
  if _stop_event is not None:
    _stop_event.set()
  if _thread is not None:
    _thread.join(timeout=5)
    _thread = None
  _stop_event = None
  logger.info("Resource monitor stopped")


if __name__ == "__main__":
  import signal
  import sys

  interval = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
  start_monitor(interval)

  try:
    signal.pause()
  except KeyboardInterrupt:
    pass
  finally:
    stop_monitor()
