"""
Naive Saga Orchestrator Service.

Exposes REST API endpoints for in-memory travel booking orchestration.
"""

from typing import Any, Dict

from fastapi import FastAPI, HTTPException, status

from coordinator import NaiveSagaCoordinator
from models import NaiveSagaInput, NaiveSagaResult


app = FastAPI(
    title='Naive Saga Orchestrator',
    description='In-memory Saga baseline with ad-hoc LIFO rollbacks',
    version='0.1.0',
)


@app.get('/health')
async def health_check() -> Dict[str, str]:
    """Basic health check endpoint."""
    return {'service': 'naive-orchestrator', 'status': 'ok'}


@app.post(
    '/book',
    response_model=NaiveSagaResult,
    status_code=status.HTTP_200_OK,
)
async def execute_booking(request: NaiveSagaInput) -> NaiveSagaResult:
    """
    Executes a single-attempt in-memory booking saga.
    State is kept exclusively in RAM; process termination destroys the compensation stack.
    """
    try:
        coordinator = NaiveSagaCoordinator()
        result = await coordinator.execute(request.model_dump())
        return result

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Coordinator execution error: {exc}',
        )
