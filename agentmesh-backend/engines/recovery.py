import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")


def generate_recovery_plan(
    failed_agent: str,
    failure_reason: str,
    blocked_output: dict,
    shared_state: dict
) -> dict:
    """
    AgentMesh Autonomous Recovery Engine.
    When an agent fails or is blocked by Circuit Breaker —
    instead of crashing, system generates an alternative plan automatically.
    No human intervention needed.
    """

    prompt = f"""
You are the AgentMesh Autonomous Recovery Engine. An AI agent has failed or been blocked. 
Your job is to generate an alternative recovery plan so the system keeps running without human help.

COMPANY GOAL: {shared_state.get('company_goal')}
BUDGET REMAINING: {shared_state.get('budget') - shared_state.get('budget_used', 0)}
DEADLINE: {shared_state.get('deadline')}
CURRENT ROUTE RISK: {shared_state.get('route_risk')}
UNITS TO DELIVER: {shared_state.get('units_to_deliver')}
CURRENT PLAN: {shared_state.get('current_plan')}

FAILED AGENT: {failed_agent}
FAILURE REASON: {failure_reason}
WHAT THE AGENT TRIED TO DO: {json.dumps(blocked_output)}

Generate a concrete alternative plan that:
1. Still achieves the company goal
2. Stays within remaining budget
3. Avoids the problem that caused the failure
4. Can be executed immediately without the failed agent

Respond ONLY in this exact JSON format, nothing else:
{{
    "recovery_possible": true or false,
    "recovery_plan": "concrete alternative action to take",
    "alternative_agent": "which other agent should handle this instead",
    "estimated_impact": "how does this affect budget, timeline, risk",
    "confidence": 0.0 to 1.0,
    "recovery_type": "reroute" or "reassign" or "reduce_scope" or "escalate",
    "reason": "why this recovery plan will work"
}}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        result = json.loads(text.strip())
        result["failed_agent"] = failed_agent
        result["failure_reason"] = failure_reason
        result["timestamp"] = __import__('datetime').datetime.now().isoformat()

        return result

    except Exception as e:
        return {
            "recovery_possible": False,
            "recovery_plan": "Manual intervention required",
            "alternative_agent": "none",
            "estimated_impact": "unknown",
            "confidence": 0.0,
            "recovery_type": "escalate",
            "reason": f"Recovery engine error: {str(e)}",
            "failed_agent": failed_agent,
            "failure_reason": failure_reason,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }


def apply_recovery(recovery_plan: dict, shared_state_instance) -> bool:
    """
    Actually applies the recovery plan to shared state.
    Updates state so all agents know recovery happened.
    Returns True if applied successfully.
    """

    try:
        if not recovery_plan.get("recovery_possible"):
            shared_state_instance.add_alert(
                message=f"Recovery failed for {recovery_plan.get('failed_agent')} — manual intervention needed",
                severity="critical"
            )
            return False

        # Update shared state with recovery info
        shared_state_instance.update(
            "current_plan",
            f"[RECOVERY] {recovery_plan.get('recovery_plan')}",
            updated_by="autonomous_recovery_engine"
        )

        shared_state_instance.add_alert(
            message=f"Auto-recovery triggered for {recovery_plan.get('failed_agent')}: {recovery_plan.get('recovery_plan')}",
            severity="info"
        )

        # Log recovery in history
        shared_state_instance.update(
            "last_recovery",
            recovery_plan,
            updated_by="autonomous_recovery_engine"
        )

        return True

    except Exception as e:
        shared_state_instance.add_alert(
            message=f"Recovery application failed: {str(e)}",
            severity="critical"
        )
        return False