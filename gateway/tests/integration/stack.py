"""Owned subprocess lifecycle and ephemeral ports for opt-in experiments."""

import asyncio
import os
import shutil
import socket
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import IO

import httpx
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter


ROOT = Path(__file__).resolve().parents[3]


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def python_executable(project: str) -> Path:
    executable = ROOT / project / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not executable.exists():
        raise RuntimeError(f'Missing {executable}; run uv sync in {project} first')
    return executable


@dataclass
class OwnedProcess:
    process: subprocess.Popen
    log_path: Path
    log_file: IO

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.log_file.close()


class LiveStack:
    def __init__(self, directory: Path, *, temporal: bool = True, barrier: bool = False):
        self.directory = directory
        self.with_temporal = temporal
        self.with_barrier = barrier
        self.processes: dict[str, OwnedProcess] = {}
        self.ports = {name: free_port() for name in ['flight', 'hotel', 'payment', 'gateway', 'temporal', 'barrier']}
        self.urls = {name: f'http://127.0.0.1:{self.ports[name]}' for name in ['flight', 'hotel', 'payment']}
        self.gateway_url = f'http://127.0.0.1:{self.ports["gateway"]}'
        self.barrier_url = f'http://127.0.0.1:{self.ports["barrier"]}'
        self.temporal_client = None
        self.namespace = f'layover-test-{uuid.uuid4().hex[:12]}'
        self.task_queue = f'booking-test-{uuid.uuid4().hex}'
        self.environment = {
            **os.environ,
            'PYTHONUNBUFFERED': '1',
            'NO_PROXY': '127.0.0.1,localhost',
            'no_proxy': '127.0.0.1,localhost',
            'TEMPORAL_HOST': f'127.0.0.1:{self.ports["temporal"]}',
            'TEMPORAL_NAMESPACE': self.namespace,
            'TEMPORAL_TASK_QUEUE': self.task_queue,
            'TEMPORAL_WEB_UI': f'http://127.0.0.1:{free_port()}',
            **{f'{name.upper()}_SERVICE_URL': url for name, url in self.urls.items()},
        }

    def spawn(self, name: str, command: list[str], *, project: str, environment: dict | None = None):
        if name in self.processes:
            self.processes.pop(name).close()
        log_path = self.directory / f'{name}-{uuid.uuid4().hex[:8]}.log'
        log_file = log_path.open('w')
        process = subprocess.Popen(
            command, cwd=ROOT / project, env=environment or self.environment,
            stdout=log_file, stderr=subprocess.STDOUT,
        )
        self.processes[name] = OwnedProcess(process, log_path, log_file)

    def kill(self, name: str) -> int:
        owned = self.processes[name]
        if owned.process.poll() is not None:
            raise RuntimeError(f'{name} stopped before the crash checkpoint: {owned.log_path.read_text()}')
        pid = owned.process.pid
        # Popen.kill is SIGKILL on POSIX, and never targets an unowned PID or container.
        owned.process.kill()
        owned.process.wait(timeout=5)
        return pid

    def assert_running(self, name: str):
        owned = self.processes[name]
        if owned.process.poll() is not None:
            raise RuntimeError(f'{name} failed to start:\n{owned.log_path.read_text()}')

    async def wait_http(self, name: str, url: str):
        async with httpx.AsyncClient(timeout=1, trust_env=False) as client:
            async with asyncio.timeout(30):
                while True:
                    self.assert_running(name)
                    try:
                        response = await client.get(url)
                        if response.status_code == 200:
                            return
                    except httpx.HTTPError:
                        pass
                    # Readiness polling only; never used to choose the crash checkpoint.
                    await asyncio.sleep(0.05)

    async def start_temporal(self):
        executable = shutil.which('temporal')
        if executable is None:
            raise RuntimeError('The Temporal CLI is required for --run-integration')
        self.spawn('temporal', [
            executable, 'server', 'start-dev', '--ip', '127.0.0.1',
            '--port', str(self.ports['temporal']), '--headless', '--namespace', self.namespace,
        ], project='gateway')

        async with asyncio.timeout(30):
            while True:
                self.assert_running('temporal')
                try:
                    self.temporal_client = await asyncio.wait_for(Client.connect(
                        self.environment['TEMPORAL_HOST'], namespace=self.namespace,
                        data_converter=pydantic_data_converter,
                    ), timeout=2)
                    await self.temporal_client.service_client.check_health()
                    return
                except (TimeoutError, RuntimeError):
                    await asyncio.sleep(0.05)

    def start_worker(self):
        project = 'orchestrators/temporal'
        self.spawn('worker', [str(python_executable(project)), 'worker.py'], project=project)

    async def start_gateway(self):
        project = 'gateway'
        self.spawn('gateway', [
            str(python_executable(project)), '-m', 'uvicorn', 'main:app',
            '--host', '127.0.0.1', '--port', str(self.ports['gateway']), '--log-level', 'warning',
        ], project=project)
        await self.wait_http('gateway', f'{self.gateway_url}/')

    async def start(self):
        for name in self.urls:
            project = f'services/{name}'
            environment = {**self.environment, f'{name.upper()}_DB_PATH': str(self.directory / f'{name}.db')}
            self.spawn(name, [
                str(python_executable(project)), '-m', 'uvicorn', 'main:app',
                '--host', '127.0.0.1', '--port', str(self.ports[name]), '--log-level', 'warning',
            ], project=project, environment=environment)
            await self.wait_http(name, f'{self.urls[name]}/health')

        if self.with_barrier:
            self.spawn('barrier', [
                str(python_executable('gateway')), str(Path(__file__).with_name('payment_barrier.py')),
                '--port', str(self.ports['barrier']), '--upstream', self.urls['payment'],
            ], project='gateway')
            await self.wait_http('barrier', f'{self.barrier_url}/health')
            self.environment['PAYMENT_SERVICE_URL'] = self.barrier_url

        if self.with_temporal:
            await self.start_temporal()
            self.start_worker()
        await self.start_gateway()

    def close(self):
        for process in reversed(list(self.processes.values())):
            process.close()
