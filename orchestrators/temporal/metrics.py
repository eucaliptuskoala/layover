"""
Prometheus metrics telemetry collector for Layover Temporal Worker.
Calculates process RSS memory, CPU time, and uptime without third-party dependencies.
"""

import os
import resource
import sys
import time

_START_TIME = time.time()


def generate_prometheus_metrics(service_name: str = 'layover-worker') -> str:
    """Generates Prometheus-formatted text metrics for process memory, CPU, and uptime."""
    rss_bytes = 0

    if os.path.exists('/proc/self/statm'):
        try:
            with open('/proc/self/statm') as f:
                parts = f.read().split()
                rss_bytes = int(parts[1]) * os.sysconf('SC_PAGE_SIZE')
        except Exception:
            pass

    if not rss_bytes:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_bytes = usage.ru_maxrss if sys.platform == 'darwin' else usage.ru_maxrss * 1024

    rss_mb = round(rss_bytes / (1024 * 1024), 2)
    cpu_seconds = round(time.process_time(), 4)
    uptime_seconds = round(time.time() - _START_TIME, 2)

    return (
        f'# HELP process_resident_memory_bytes Resident memory size in bytes.\n'
        f'# TYPE process_resident_memory_bytes gauge\n'
        f'process_resident_memory_bytes{{service="{service_name}"}} {rss_bytes}\n\n'
        f'# HELP process_resident_memory_megabytes Resident memory size in megabytes.\n'
        f'# TYPE process_resident_memory_megabytes gauge\n'
        f'process_resident_memory_megabytes{{service="{service_name}"}} {rss_mb}\n\n'
        f'# HELP process_cpu_seconds_total Total user and system CPU time spent in seconds.\n'
        f'# TYPE process_cpu_seconds_total counter\n'
        f'process_cpu_seconds_total{{service="{service_name}"}} {cpu_seconds}\n\n'
        f'# HELP process_uptime_seconds Total seconds elapsed since process start.\n'
        f'# TYPE process_uptime_seconds counter\n'
        f'process_uptime_seconds{{service="{service_name}"}} {uptime_seconds}\n\n'
        f'# HELP layover_service_up Status indicator of the service process.\n'
        f'# TYPE layover_service_up gauge\n'
        f'layover_service_up{{service="{service_name}"}} 1\n'
    )
