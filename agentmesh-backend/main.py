import os
import asyncio
from datetime import datetime
from typing import Any, Callable

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()


# ============================================================
# CORE IMPORTS
# ============================================================

from shared_state import shared_state

from engines.agent_monitor import agent_monitor
from engines.alignment import score_alignment, calculate_overall_alignment
from engines.circuit_breaker import validate_output
from engines.recovery import generate_recovery_plan, apply_recovery


# Supports both the correct and the existing misspelled filename.
try:
    from engines.arbitration import detect_conflict, arbitrate
except ImportError:
    from engines.arbiration import detect_conflict, arbitrate


# ============================================================
# AGENT IMPORTS
# ============================================================

from agents.risk import run as risk_run
from agents.logistics import run as logistics_run
from agents.finance import run as finance_run
from agents.operations import run as operations_run

from agents.cost_optimizer import cost_optimizer_agent
from agents.supply_checker import supply_checker_agent


# ============================================================
# AGENT REGISTRY
# ============================================================

PIPELINE_AGENTS: dict[str, Callable[[dict], dict]] = {
    "risk": risk_run,
    "logistics": logistics_run,
    "finance": finance_run,
    "cost_optimizer": cost_optimizer_agent,
    "operations": operations_run,
}


AGENT_MAP: dict[str, Callable[[dict], dict]] = {
    **PIPELINE_AGENTS,
    "supply_checker": supply_checker_agent,
}


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="AgentMesh OS",
    version="1.0.0",
    description="Agent Intelligence and Coordination Platform",
)


# ============================================================
# CORS CONFIGURATION
# ============================================================

frontend_origins = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
)

allowed_origins = [
    origin.strip().rstrip("/")
    for origin in frontend_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# APPLICATION STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():
    """Register all known agents when the application starts."""

    for agent_name in AGENT_MAP:
        agent_monitor.register_agent(agent_name)


# ============================================================
# WEBSOCKET MANAGEMENT
# ============================================================

active_connections: list[WebSocket] = []


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Maintain a live WebSocket connection with the frontend."""

    await websocket.accept()
    active_connections.append(websocket)

    await websocket.send_json(
        {
            "type": "connected",
            "system": "AgentMesh OS",
            "timestamp": datetime.now().isoformat(),
        }
    )

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)

    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)


async def broadcast(data: dict):
    """Broadcast a message to all connected frontend clients."""

    disconnected_connections = []

    for connection in active_connections:
        try:
            await connection.send_json(data)

        except Exception:
            disconnected_connections.append(connection)

    for connection in disconnected_connections:
        if connection in active_connections:
            active_connections.remove(connection)


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def normalize_confidence(
    value: Any,
    default: float = 0.5,
) -> float:
    """Normalize confidence values to a range between 0.0 and 1.0."""

    try:
        confidence = float(value)

        if confidence > 1:
            confidence = confidence / 100

        return max(0.0, min(1.0, confidence))

    except (TypeError, ValueError):
        return default


def update_state_from_agent_output(
    agent_name: str,
    output: dict,
):
    """Update the shared organizational state using validated agent output."""

    if agent_name == "risk":
        route_risk = output.get("route_risk_update")

        if route_risk:
            shared_state.update(
                "route_risk",
                route_risk,
                updated_by="risk",
            )

    elif agent_name == "logistics":
        selected_route = output.get("route_selected")
        selected_warehouse = output.get("warehouse_selected")

        if selected_route:
            shared_state.update(
                "route",
                selected_route,
                updated_by="logistics",
            )

        if selected_warehouse:
            shared_state.update(
                "warehouse_status",
                selected_warehouse,
                updated_by="logistics",
            )

    elif agent_name == "finance":
        estimated_cost = output.get("estimated_cost")

        if isinstance(estimated_cost, (int, float)):
            shared_state.update(
                "budget_used",
                estimated_cost,
                updated_by="finance",
            )

    elif agent_name == "operations":
        recommendation = output.get("recommendation")

        if recommendation:
            shared_state.update(
                "current_plan",
                recommendation,
                updated_by="operations",
            )


def get_extended_sprawl_warnings() -> list:
    """
    Return standard sprawl warnings and immediately flag agents
    that are registered but have never been executed.
    """

    warnings = list(agent_monitor.get_sprawl_warnings())

    known_warning_agents = {
        warning.get("agent")
        for warning in warnings
    }

    for agent in agent_monitor.get_all_agent_health():
        if (
            agent.get("total_runs", 0) == 0
            and agent.get("name") not in known_warning_agents
        ):
            warnings.append(
                {
                    "type": "unused_agent",
                    "agent": agent.get("name"),
                    "message": (
                        f"{agent.get('name')} is registered "
                        "but has never been executed."
                    ),
                    "severity": "warning",
                }
            )

    return warnings


def flatten_agent_outputs() -> dict:
    """Return stored agent outputs without internal storage wrappers."""

    stored_outputs = shared_state.get_all_agent_outputs()

    return {
        agent_name: stored_data.get(
            "output",
            stored_data,
        )
        for agent_name, stored_data in stored_outputs.items()
    }


# ============================================================
# MAIN AGENTMESH PIPELINE
# ============================================================

@app.post("/run")
async def run_agents():
    """
    Execute the complete AgentMesh pipeline.

    Pipeline order:
    Risk -> Logistics -> Finance -> Cost Optimizer -> Operations

    Each output is processed through:
    Circuit Breaker -> Shared State Update -> Alignment Scoring

    After execution:
    Conflict Detection -> Arbitration -> Similarity Detection
    """

    results = {
        "timestamp": datetime.now().isoformat(),
        "agent_outputs": {},
        "circuit_breaker_results": {},
        "alignment_scores": {},
        "overall_alignment": 100.0,
        "conflict": None,
        "arbitration": None,
        "similarity_report": None,
        "recovery_triggered": False,
        "recovery_plans": [],
        "agent_health": [],
        "sprawl_warnings": [],
        "alerts": [],
        "final_state": {},
    }

    valid_outputs = {}
    alignment_values = []

    for agent_name, agent_runner in PIPELINE_AGENTS.items():
        current_state = shared_state.get()

        await broadcast(
            {
                "type": "agent_started",
                "agent": agent_name,
                "timestamp": datetime.now().isoformat(),
            }
        )

        agent_monitor.mark_active(agent_name)

        try:
            output = await asyncio.to_thread(
                agent_runner,
                current_state,
            )

            if not isinstance(output, dict):
                raise ValueError(
                    f"{agent_name} returned an invalid output type."
                )

            output["agent"] = agent_name
            output["confidence"] = normalize_confidence(
                output.get("confidence")
            )

            shared_state.store_agent_output(
                agent_name,
                output,
            )

            results["agent_outputs"][agent_name] = output

            await broadcast(
                {
                    "type": "agent_output",
                    "agent": agent_name,
                    "output": output,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            validation_state = shared_state.get()

            circuit_result = await asyncio.to_thread(
                validate_output,
                agent_name,
                output,
                validation_state,
            )

            results["circuit_breaker_results"][
                agent_name
            ] = circuit_result

            shared_state.log_circuit_breaker(
                agent_name,
                output,
                circuit_result.get(
                    "reason",
                    "No validation reason was provided.",
                ),
                blocked=not circuit_result.get(
                    "valid",
                    False,
                ),
            )

            await broadcast(
                {
                    "type": "circuit_breaker",
                    "agent": agent_name,
                    "result": circuit_result,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            if not circuit_result.get("valid", False):
                failure_reason = circuit_result.get(
                    "reason",
                    "The output was blocked by the Circuit Breaker.",
                )

                agent_monitor.mark_failed(
                    agent_name,
                    failure_reason,
                )

                shared_state.add_alert(
                    f"{agent_name} blocked: {failure_reason}",
                    severity="warning",
                )

                recovery_plan = await asyncio.to_thread(
                    generate_recovery_plan,
                    agent_name,
                    failure_reason,
                    output,
                    validation_state,
                )

                recovery_applied = await asyncio.to_thread(
                    apply_recovery,
                    recovery_plan,
                    shared_state,
                )

                results["recovery_triggered"] = True

                results["recovery_plans"].append(
                    {
                        "agent": agent_name,
                        "applied": recovery_applied,
                        "plan": recovery_plan,
                    }
                )

                await broadcast(
                    {
                        "type": "recovery_triggered",
                        "agent": agent_name,
                        "recovery": recovery_plan,
                        "applied": recovery_applied,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                continue

            update_state_from_agent_output(
                agent_name,
                output,
            )

            valid_outputs[agent_name] = {
                "output": output,
                "timestamp": datetime.now().isoformat(),
            }

            agent_monitor.mark_success(
                agent_name,
                output.get("recommendation", ""),
            )

            alignment_state = shared_state.get()

            alignment_result = await asyncio.to_thread(
                score_alignment,
                agent_name,
                output,
                alignment_state,
            )

            results["alignment_scores"][
                agent_name
            ] = alignment_result

            alignment_values.append(
                float(
                    alignment_result.get(
                        "score",
                        50,
                    )
                )
            )

            await broadcast(
                {
                    "type": "alignment_scored",
                    "agent": agent_name,
                    "alignment": alignment_result,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except Exception as error:
            error_message = str(error)

            agent_monitor.mark_failed(
                agent_name,
                error_message,
            )

            shared_state.add_alert(
                f"{agent_name} crashed: {error_message}",
                severity="critical",
            )

            results["agent_outputs"][agent_name] = {
                "agent": agent_name,
                "error": error_message,
                "confidence": 0.0,
            }

            recovery_state = shared_state.get()

            recovery_plan = await asyncio.to_thread(
                generate_recovery_plan,
                agent_name,
                error_message,
                {},
                recovery_state,
            )

            recovery_applied = await asyncio.to_thread(
                apply_recovery,
                recovery_plan,
                shared_state,
            )

            results["recovery_triggered"] = True

            results["recovery_plans"].append(
                {
                    "agent": agent_name,
                    "applied": recovery_applied,
                    "plan": recovery_plan,
                }
            )

            await broadcast(
                {
                    "type": "agent_crashed",
                    "agent": agent_name,
                    "error": error_message,
                    "recovery": recovery_plan,
                    "applied": recovery_applied,
                    "timestamp": datetime.now().isoformat(),
                }
            )

    if len(valid_outputs) >= 2:
        conflict_result = await asyncio.to_thread(
            detect_conflict,
            valid_outputs,
        )

        results["conflict"] = conflict_result

        await broadcast(
            {
                "type": "conflict_check",
                "result": conflict_result,
                "timestamp": datetime.now().isoformat(),
            }
        )

        if conflict_result.get(
            "conflict_detected",
            False,
        ):
            arbitration_result = await asyncio.to_thread(
                arbitrate,
                valid_outputs,
                shared_state.get(),
            )

            results["arbitration"] = arbitration_result

            shared_state.log_conflict(
                conflict_result.get(
                    "conflicting_agents",
                    [],
                ),
                arbitration_result.get(
                    "winner",
                    "unknown",
                ),
                arbitration_result.get(
                    "reasoning",
                    "No arbitration reasoning was provided.",
                ),
            )

            final_decision = arbitration_result.get("decision")

            if final_decision:
                shared_state.update(
                    "current_plan",
                    final_decision,
                    updated_by="arbitration_engine",
                )

            await broadcast(
                {
                    "type": "arbitration_complete",
                    "result": arbitration_result,
                    "timestamp": datetime.now().isoformat(),
                }
            )

    overall_alignment = calculate_overall_alignment(
        alignment_values
    )

    results["overall_alignment"] = overall_alignment

    shared_state.update(
        "alignment_score",
        overall_alignment,
        updated_by="alignment_engine",
    )

    try:
        similarity_report = await asyncio.to_thread(
            agent_monitor.detect_similar_agents,
            shared_state.get_all_agent_outputs(),
        )

    except Exception as error:
        similarity_report = {
            "similarity_detected": False,
            "similar_pairs": [],
            "summary": (
                f"Similarity detection failed: {str(error)}"
            ),
        }

    results["similarity_report"] = similarity_report
    results["agent_health"] = agent_monitor.get_all_agent_health()
    results["sprawl_warnings"] = get_extended_sprawl_warnings()
    results["alerts"] = shared_state.get().get("alerts", [])
    results["final_state"] = shared_state.get()

    await broadcast(
        {
            "type": "run_complete",
            "results": results,
            "state": results["final_state"],
            "timestamp": datetime.now().isoformat(),
        }
    )

    return results


# ============================================================
# INDIVIDUAL AGENT EXECUTION
# ============================================================

@app.post("/run/{agent_name}")
async def run_single_agent(agent_name: str):
    """Execute one registered agent independently."""

    if agent_name not in AGENT_MAP:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Unknown agent: {agent_name}",
                "available_agents": list(AGENT_MAP.keys()),
            },
        )

    agent_runner = AGENT_MAP[agent_name]
    current_state = shared_state.get()

    agent_monitor.mark_active(agent_name)

    await broadcast(
        {
            "type": "agent_started",
            "agent": agent_name,
            "mode": "single",
            "timestamp": datetime.now().isoformat(),
        }
    )

    try:
        output = await asyncio.to_thread(
            agent_runner,
            current_state,
        )

        if not isinstance(output, dict):
            raise ValueError(
                f"{agent_name} returned an invalid output type."
            )

        output["agent"] = agent_name
        output["confidence"] = normalize_confidence(
            output.get("confidence")
        )

        shared_state.store_agent_output(
            agent_name,
            output,
        )

        agent_monitor.mark_success(
            agent_name,
            output.get("recommendation", ""),
        )

        await broadcast(
            {
                "type": "single_agent_complete",
                "agent": agent_name,
                "output": output,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return {
            "agent": agent_name,
            "status": "completed",
            "output": output,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as error:
        agent_monitor.mark_failed(
            agent_name,
            str(error),
        )

        shared_state.add_alert(
            f"{agent_name} manual run failed: {str(error)}",
            severity="critical",
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# ============================================================
# DASHBOARD ENDPOINT
# ============================================================

@app.get("/dashboard")
def get_dashboard():
    """Return all primary dashboard information in one response."""

    state = shared_state.get()
    agents = agent_monitor.get_all_agent_health()
    agent_outputs = flatten_agent_outputs()

    active_agents = [
        agent
        for agent in agents
        if agent.get("status") == "active"
    ]

    failed_agents = [
        agent
        for agent in agents
        if agent.get("status") == "failed"
    ]

    unused_agents = [
        agent
        for agent in agents
        if agent.get("total_runs", 0) == 0
    ]

    confidence_values = []

    for output in agent_outputs.values():
        if isinstance(output, dict):
            confidence_values.append(
                normalize_confidence(
                    output.get("confidence")
                )
            )

    system_confidence = (
        round(
            (
                sum(confidence_values)
                / len(confidence_values)
            )
            * 100,
            1,
        )
        if confidence_values
        else 0.0
    )

    return {
        "system": "AgentMesh OS",
        "state": state,
        "agents": agents,
        "agent_outputs": agent_outputs,
        "conflicts": shared_state.conflict_log,
        "circuit_breaker_log": shared_state.circuit_breaker_log,
        "alerts": state.get("alerts", []),
        "sprawl_warnings": get_extended_sprawl_warnings(),
        "stats": {
            "registered_agents": len(agents),
            "active_agents": len(active_agents),
            "failed_agents": len(failed_agents),
            "unused_agents": len(unused_agents),
            "conflicts": len(shared_state.conflict_log),
            "alignment_score": state.get(
                "alignment_score",
                100,
            ),
            "system_confidence": system_confidence,
        },
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================
# FRONTEND DATA ENDPOINTS
# ============================================================

@app.get("/state")
def get_state():
    return shared_state.get()


@app.get("/history")
def get_history():
    return {
        "history": shared_state.get_history(),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/alerts")
def get_alerts():
    return {
        "alerts": shared_state.get().get("alerts", []),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/conflicts")
def get_conflicts():
    return {
        "conflicts": shared_state.conflict_log,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/alignment")
def get_alignment():
    return {
        "alignment_score": shared_state.get().get(
            "alignment_score",
            100,
        ),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/agent-health")
def get_agent_health():
    return {
        "agents": agent_monitor.get_all_agent_health(),
        "sprawl_warnings": get_extended_sprawl_warnings(),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/agent-outputs")
def get_agent_outputs():
    return {
        "agent_outputs": flatten_agent_outputs(),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/circuit-breaker-log")
def get_circuit_breaker_log():
    return {
        "events": shared_state.circuit_breaker_log,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/recovery-log")
def get_recovery_log():
    history = shared_state.get_history()

    recovery_events = [
        event
        for event in history
        if event.get("updated_by")
        == "autonomous_recovery_engine"
    ]

    return {
        "recovery_events": recovery_events,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/similarity")
async def get_similarity():
    try:
        return await asyncio.to_thread(
            agent_monitor.detect_similar_agents,
            shared_state.get_all_agent_outputs(),
        )

    except Exception as error:
        return {
            "similarity_detected": False,
            "similar_pairs": [],
            "summary": (
                f"Similarity detection failed: {str(error)}"
            ),
        }


# ============================================================
# HEALTH AND ROOT ENDPOINTS
# ============================================================

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "system": "AgentMesh OS",
        "version": "1.0.0",
        "registered_agents": list(AGENT_MAP.keys()),
        "pipeline_agents": list(PIPELINE_AGENTS.keys()),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/")
def root():
    return {
        "system": "AgentMesh OS",
        "status": "running",
        "version": "1.0.0",
        "documentation": "/docs",
        "health": "/health",
        "dashboard": "/dashboard",
        "pipeline": "POST /run",
        "single_agent": "POST /run/{agent_name}",
        "websocket": "/ws",
        "registered_agents": list(AGENT_MAP.keys()),
        "pipeline_agents": list(PIPELINE_AGENTS.keys()),
    }


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":
    import uvicorn

    port = int(
        os.getenv(
            "PORT",
            "8000",
        )
    )

    environment = os.getenv(
        "ENVIRONMENT",
        "development",
    )

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=environment == "development",
    )