from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from datetime import datetime

# AgentMesh core imports
from shared_state import shared_state

# AgentMesh engines
from engines.circuit_breaker import validate_output
from engines.arbitration import detect_conflict, arbitrate
from engines.alignment import score_alignment, calculate_overall_alignment
from engines.agent_monitor import agent_monitor
from engines.recovery import generate_recovery_plan, apply_recovery

# Ishita's agents
from agents.finance import finance_agent
from agents.risk import risk_agent
from agents.logistics import logistics_agent
from agents.operations import operations_agent

app = FastAPI(title="AgentMesh OS", version="1.0.0")

# CORS — React frontend ko allow karo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections tracker
active_connections: list[WebSocket] = []


# ─────────────────────────────────────────
# WebSocket — live frontend updates
# ─────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)


async def broadcast(data: dict):
    """Send live update to all connected frontend clients."""
    message = json.dumps(data)
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except:
            disconnected.append(connection)
    for conn in disconnected:
        active_connections.remove(conn)


# ─────────────────────────────────────────
# MAIN ROUTE — POST /run
# This is the heart of AgentMesh OS
# ─────────────────────────────────────────

@app.post("/run")
async def run_agents():
    """
    Runs all 4 agents through the full AgentMesh pipeline:
    1. Run agents
    2. Circuit Breaker validates each output
    3. Arbitration detects and resolves conflicts
    4. Alignment scores every action
    5. Agent Monitor tracks health
    6. Recovery triggers if any agent fails
    7. WebSocket broadcasts live updates
    """

    results = {
        "timestamp": datetime.now().isoformat(),
        "agent_outputs": {},
        "circuit_breaker_results": {},
        "conflict": None,
        "arbitration": None,
        "alignment_scores": {},
        "overall_alignment": 100,
        "recovery_triggered": False,
        "recovery_plan": None,
        "agent_health": [],
        "alerts": [],
        "similarity_report": None,
    }

    current_state = shared_state.get()
    agent_functions = {
        "finance": finance_agent,
        "risk": risk_agent,
        "logistics": logistics_agent,
        "operations": operations_agent,
    }

    valid_outputs = {}
    alignment_scores = []

    # ── STEP 1: Run each agent + Circuit Breaker + Alignment ──
    for agent_name, agent_fn in agent_functions.items():

        await broadcast({
            "type": "agent_started",
            "agent": agent_name,
            "timestamp": datetime.now().isoformat()
        })

        # Agent Monitor — mark active
        agent_monitor.mark_active(agent_name)

        try:
            # Run agent (Ishita's function)
            output = agent_fn(current_state)
            shared_state.store_agent_output(agent_name, output)
            results["agent_outputs"][agent_name] = output

            await broadcast({
                "type": "agent_output",
                "agent": agent_name,
                "output": output
            })

            # ── STEP 2: Circuit Breaker ──
            cb_result = validate_output(agent_name, output, current_state)
            results["circuit_breaker_results"][agent_name] = cb_result
            shared_state.log_circuit_breaker(
                agent_name, output,
                cb_result["reason"],
                blocked=not cb_result["valid"]
            )

            await broadcast({
                "type": "circuit_breaker",
                "agent": agent_name,
                "result": cb_result
            })

            if not cb_result["valid"]:
                # Circuit Breaker blocked this agent
                agent_monitor.mark_failed(agent_name, cb_result["reason"])
                shared_state.add_alert(
                    f"{agent_name} blocked: {cb_result['reason']}",
                    severity="warning"
                )

                # ── STEP 3: Autonomous Recovery ──
                recovery = generate_recovery_plan(
                    agent_name,
                    cb_result["reason"],
                    output,
                    current_state
                )
                applied = apply_recovery(recovery, shared_state)
                results["recovery_triggered"] = True
                results["recovery_plan"] = recovery

                await broadcast({
                    "type": "recovery_triggered",
                    "agent": agent_name,
                    "recovery": recovery,
                    "applied": applied
                })

            else:
                # Valid output — store for arbitration
                valid_outputs[agent_name] = {
                    "output": output,
                    "timestamp": datetime.now().isoformat()
                }
                agent_monitor.mark_success(
                    agent_name,
                    output.get("recommendation", "")
                )

                # ── STEP 4: Alignment Scoring ──
                alignment = score_alignment(agent_name, output, current_state)
                results["alignment_scores"][agent_name] = alignment
                alignment_scores.append(alignment["score"])

                await broadcast({
                    "type": "alignment_scored",
                    "agent": agent_name,
                    "alignment": alignment
                })

        except Exception as e:
            # Agent itself crashed
            agent_monitor.mark_failed(agent_name, str(e))
            shared_state.add_alert(
                f"{agent_name} crashed: {str(e)}",
                severity="critical"
            )
            results["agent_outputs"][agent_name] = {
                "error": str(e),
                "agent": agent_name
            }

            # Recovery for crashed agent
            recovery = generate_recovery_plan(
                agent_name, str(e), {}, current_state
            )
            apply_recovery(recovery, shared_state)
            results["recovery_triggered"] = True
            results["recovery_plan"] = recovery

            await broadcast({
                "type": "agent_crashed",
                "agent": agent_name,
                "error": str(e),
                "recovery": recovery
            })

    # ── STEP 5: Conflict Detection + Arbitration ──
    if len(valid_outputs) >= 2:
        conflict_result = detect_conflict(valid_outputs)
        results["conflict"] = conflict_result

        await broadcast({
            "type": "conflict_check",
            "result": conflict_result
        })

        if conflict_result["conflict_detected"]:
            arbitration_result = arbitrate(valid_outputs, current_state)
            results["arbitration"] = arbitration_result

            shared_state.log_conflict(
                conflict_result["conflicting_agents"],
                arbitration_result["winner"],
                arbitration_result["reasoning"]
            )

            # Update state with winning decision
            shared_state.update(
                "current_plan",
                arbitration_result["decision"],
                updated_by="arbitration_engine"
            )

            await broadcast({
                "type": "arbitration_complete",
                "result": arbitration_result
            })

    # ── STEP 6: Overall Alignment Score ──
    overall = calculate_overall_alignment(alignment_scores)
    results["overall_alignment"] = overall
    shared_state.update(
        "alignment_score",
        overall,
        updated_by="alignment_engine"
    )

    # ── STEP 7: Agent Health + Similarity ──
    results["agent_health"] = agent_monitor.get_all_agent_health()
    results["similarity_report"] = agent_monitor.detect_similar_agents(
        shared_state.get_all_agent_outputs()
    )
    results["alerts"] = shared_state.get()["alerts"]

    # Final broadcast
    await broadcast({
        "type": "run_complete",
        "results": results,
        "state": shared_state.get()
    })

    return results


# ─────────────────────────────────────────
# GET ROUTES — Dashboard data
# ─────────────────────────────────────────

@app.get("/state")
def get_state():
    """Current shared state — all agents read this."""
    return shared_state.get()


@app.get("/history")
def get_history():
    """Full audit trail — every state change logged."""
    return shared_state.get_history()


@app.get("/alerts")
def get_alerts():
    """All alerts — circuit breaker blocks, alignment drops, crashes."""
    return shared_state.get()["alerts"]


@app.get("/conflicts")
def get_conflicts():
    """Conflict log — who disagreed, who won, why."""
    return shared_state.conflict_log


@app.get("/alignment")
def get_alignment():
    """Current alignment score."""
    return {
        "alignment_score": shared_state.get()["alignment_score"],
        "timestamp": datetime.now().isoformat()
    }


@app.get("/agent-health")
def get_agent_health():
    """Agent health report — status, ROI, idle time."""
    return {
        "agents": agent_monitor.get_all_agent_health(),
        "sprawl_warnings": agent_monitor.get_sprawl_warnings(),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/circuit-breaker-log")
def get_circuit_breaker_log():
    """All circuit breaker events — what got blocked and why."""
    return shared_state.circuit_breaker_log


@app.get("/recovery-log")
def get_recovery_log():
    """Recovery history — what failed, what alternative was generated."""
    return shared_state.get_history()


@app.get("/similarity")
def get_similarity():
    """Agent similarity report — who is doing duplicate work."""
    return agent_monitor.detect_similar_agents(
        shared_state.get_all_agent_outputs()
    )


@app.get("/")
def root():
    return {
        "system": "AgentMesh OS",
        "status": "running",
        "version": "1.0.0",
        "engines": [
            "circuit_breaker",
            "arbitration",
            "alignment",
            "agent_monitor",
            "recovery"
        ],
        "routes": [
            "POST /run",
            "GET /state",
            "GET /history",
            "GET /alerts",
            "GET /conflicts",
            "GET /alignment",
            "GET /agent-health",
            "GET /circuit-breaker-log",
            "GET /similarity",
            "WS /ws"
        ]
    }