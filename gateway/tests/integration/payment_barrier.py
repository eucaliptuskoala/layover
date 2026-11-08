"""Loopback-only test proxy. Not imported by or exposed from any production app."""

import argparse
import asyncio

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import Response


def create_barrier(upstream: str) -> FastAPI:
    app = FastAPI()
    arrived = asyncio.Event()
    released = asyncio.Event()
    declined = asyncio.Event()
    observed = {}

    @app.get('/health')
    async def health():
        return {'status': 'ok'}

    @app.get('/test/wait-for-payment')
    async def wait_for_payment():
        await arrived.wait()
        return observed

    @app.post('/test/release')
    async def release():
        released.set()
        return {'released': True}

    @app.get('/test/wait-for-decline')
    async def wait_for_decline():
        await declined.wait()
        return observed

    @app.post('/charge')
    async def charge(request: Request):
        body = await request.json()
        observed['booking_id'] = body['booking_id']
        arrived.set()
        await released.wait()
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            response = await client.post(f'{upstream}/charge', json=body)
        observed['status_code'] = response.status_code
        declined.set()
        return Response(response.content, status_code=response.status_code, media_type='application/json')

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--upstream', required=True)
    args = parser.parse_args()
    uvicorn.run(create_barrier(args.upstream), host='127.0.0.1', port=args.port, log_level='warning')
