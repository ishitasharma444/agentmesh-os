"""
crew_runner.py — AgentMesh OS
Runs all 4 CrewAI agents together with SharedState coordination.
Use this file to test the full pipeline locally without FastAPI.
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
from datetime import datetime

try:
    from shared_state import shared_state
    print("[AgentMesh] Using shared_state singleton from shared_state.py")
except ImportError:
    class _SharedState:
        def __init__(self):
            self.state = {
                "company_goal": "Deliver 500 units to Mumbai by Friday within 2L budget",
                "budget": 200000,
                "budget_used": 0,
                "route": None,
                "route_risk": "unknown",
                "warehouse_status": "available",
                "deadline": "Friday",
                "units_to_deliver": 500,
                "current_plan": None,
                "alerts": [],
                "alignment_score": 100,
                "last_recovery": None,
            }
            self.history = []
            self.agent_outputs = {}
            self.conflict_log = []
            self.circuit_breaker_log = []

        def get(self):
            return self.state.copy()

        def update(self, key, value, updated_by):
            old = self.state.get(key)
            self.state[key] = value
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "updated_by": updated_by,
                "key": key,
                "old_value": old,
                "new_value": value,
            })

        def store_agent_output(self, agent_name, output):
            self.agent_outputs[agent_name] = {
                "output": output,
                "timestamp": datetime.now().isoformat()
            }

        def get_all_agent_outputs(self):
            return self.agent_outputs

    shared_state = _SharedState()
    print("[AgentMesh] Using inline SharedState")

from agents.logistics import run as logistics_run
from agents.finance import run as finance_run
from agents.risk import run as risk_run
from agents.operations import run as operations_run


def log(msg: str):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def run_agent(name: str, runner_fn, state: dict) -> dict:
    log(f"▶ Running {name.upper()} agent...")
    try:
        output = runner_fn(state)
        shared_state.store_agent_output(name, output)
        log(f"✓ {name.upper()} complete — confidence: {output.get('confidence', '?')}")
        log(f"  Recommendation: {output.get('recommendation', '')}")
        return output
    except Exception as e:
        log(f"✗ {name.upper()} FAILED: {e}")
        return {
            "agent": name,
            "recommendation": f"Agent failed: {str(e)}",
            "confidence": 0.0,
            "reasoning": str(e)
        }


def update_state_from_outputs(outputs: dict):
    if "logistics" in outputs:
        lg = outputs["logistics"]
        if lg.get("route_selected"):
            shared_state.update("route", lg["route_selected"], "logistics")
        if lg.get("warehouse_selected"):
            shared_state.update("warehouse_status", lg["warehouse_selected"], "logistics")

    if "risk" in outputs:
        rk = outputs["risk"]
        if rk.get("route_risk_update"):
            shared_state.update("route_risk", rk["route_risk_update"], "risk")
        if rk.get("overall_risk_level") in ["high", "critical"]:
            shared_state.state["alerts"].append({
                "timestamp": datetime.now().isoformat(),
                "message": f"Risk Agent flagged {rk['overall_risk_level']} risk: {rk.get('recommendation', '')}",
                "severity": "critical" if rk["overall_risk_level"] == "critical" else "warning"
            })

    if "finance" in outputs:
        fn = outputs["finance"]
        if fn.get("estimated_cost"):
            shared_state.update("budget_used", fn["estimated_cost"], "finance")
        if not fn.get("budget_compliance", True):
            shared_state.state["alerts"].append({
                "timestamp": datetime.now().isoformat(),
                "message": f"Finance Agent: Budget FAILED — estimated ₹{fn.get('estimated_cost')} exceeds limit",
                "severity": "critical"
            })

    if "operations" in outputs:
        op = outputs["operations"]
        plan_summary = f"{op.get('transport_mode', 'unknown')} | {op.get('vehicle_type', 'unknown')} | ETA: {op.get('execution_timeline', {}).get('arrival', 'unknown')}"
        shared_state.update("current_plan", plan_summary, "operations")


def detect_conflicts(outputs: dict) -> list:
    conflicts = []

    if "finance" in outputs and "risk" in outputs:
        fn_ok = outputs["finance"].get("budget_compliance", True)
        risk_level = outputs["risk"].get("overall_risk_level", "unknown")
        if fn_ok and risk_level in ["high", "critical"]:
            conflicts.append({
                "agents": ["finance", "risk"],
                "conflict": f"Finance approves plan but Risk flags {risk_level} risk",
                "resolution": "Risk agent wins — safety over cost"
            })

    if "logistics" in outputs and "risk" in outputs:
        risks = outputs["risk"].get("identified_risks", [])
        if any("route" in str(r).lower() for r in risks) and outputs["risk"].get("overall_risk_level") in ["high", "critical"]:
            conflicts.append({
                "agents": ["logistics", "risk"],
                "conflict": "Logistics selected a route that Risk has flagged as dangerous",
                "resolution": "Circuit Breaker blocks logistics output — re-planning triggered"
            })

    return conflicts


async def run_all_agents():
    log("=" * 60)
    log("AgentMesh OS — Full Pipeline Starting")
    log("=" * 60)

    state = shared_state.get()
    log(f"Company Goal: {state['company_goal']}")
    log(f"Budget: ₹{state['budget']} | Units: {state['units_to_deliver']} | Deadline: {state['deadline']}")

    # Risk pehle — baaki agents uski info dekhein
    risk_output = run_agent("risk", risk_run, shared_state.get())
    if risk_output.get("route_risk_update"):
        shared_state.update("route_risk", risk_output["route_risk_update"], "risk")

    # Logistics — risk aware
    logistics_output = run_agent("logistics", logistics_run, shared_state.get())
    if logistics_output.get("route_selected"):
        shared_state.update("route", logistics_output["route_selected"], "logistics")

    # Finance — logistics plan aware
    finance_output = run_agent("finance", finance_run, shared_state.get())

    # Operations — full picture
    operations_output = run_agent("operations", operations_run, shared_state.get())

    all_outputs = {
        "risk": risk_output,
        "logistics": logistics_output,
        "finance": finance_output,
        "operations": operations_output,
    }

    log("\n── Updating SharedState...")
    update_state_from_outputs(all_outputs)

    log("\n── Running Conflict Detection...")
    conflicts = detect_conflicts(all_outputs)
    if conflicts:
        log(f"⚠ {len(conflicts)} conflict(s) detected:")
        for c in conflicts:
            log(f"  {c['agents']} → {c['conflict']}")
            log(f"  Resolution: {c['resolution']}")
    else:
        log("✓ No conflicts detected")

    final_state = shared_state.get()
    log("\n" + "=" * 60)
    log("FINAL SUMMARY")
    log("=" * 60)
    log(f"Route:           {final_state.get('route', 'Not set')}")
    log(f"Route Risk:      {final_state.get('route_risk', 'unknown')}")
    log(f"Budget Used:     ₹{final_state.get('budget_used', 0)} / ₹{final_state.get('budget', 200000)}")
    log(f"Current Plan:    {final_state.get('current_plan', 'Not set')}")
    log(f"Alerts:          {len(final_state.get('alerts', []))} alert(s)")

    log("\n── Agent Confidence Scores:")
    for name, output in all_outputs.items():
        conf = output.get("confidence", 0)
        bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
        log(f"  {name:<12} [{bar}] {conf:.0%}")

    log("\n[AgentMesh] Pipeline complete.\n")
    return {
        "agent_outputs": all_outputs,
        "final_state": final_state,
        "conflicts": conflicts,
    }


if __name__ == "__main__":
    asyncio.run(run_all_agents())