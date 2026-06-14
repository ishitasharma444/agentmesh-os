import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

def detect_conflict(agent_outputs: dict) -> dict:
    """
    AgentMesh Conflict Detector — checks if agents are recommending opposite things.
    Example: Finance says Route B (cheap), Risk says Route A (safe) — that's a conflict.
    """

    agents = list(agent_outputs.keys())
    recommendations = {
        name: data["output"].get("recommendation", "") 
        for name, data in agent_outputs.items()
    }

    prompt = f"""
You are the AgentMesh Conflict Detector. Check if these AI agents are recommending conflicting actions.

AGENT RECOMMENDATIONS:
{json.dumps(recommendations, indent=2)}

A conflict exists when agents recommend opposite or incompatible actions.
Example conflicts:
- Finance says "use Route B" but Risk says "avoid Route B"
- Logistics says "ship today" but Operations says "delay shipment"

Respond ONLY in this exact JSON format, nothing else:
{{
    "conflict_detected": true or false,
    "conflicting_agents": ["agent1", "agent2"],
    "conflict_summary": "one line describing what they disagree on"
}}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        return json.loads(text.strip())

    except Exception as e:
        return {
            "conflict_detected": False,
            "conflicting_agents": [],
            "conflict_summary": f"Detection error: {str(e)}"
        }


def arbitrate(agent_outputs: dict, shared_state: dict) -> dict:
    """
    AgentMesh Arbitration Engine — when conflict detected, picks a winner.
    Uses company goal as the deciding factor — not just agent confidence.
    Full reasoning is logged so judges can see HOW the decision was made.
    """

    prompt = f"""
You are the AgentMesh Arbitration Engine. Multiple AI agents disagree. You must pick a winner based on the company goal.

COMPANY GOAL: {shared_state.get('company_goal')}
BUDGET: {shared_state.get('budget')}
BUDGET USED: {shared_state.get('budget_used')}
ROUTE RISK: {shared_state.get('route_risk')}

ALL AGENT OUTPUTS:
{json.dumps({name: data["output"] for name, data in agent_outputs.items()}, indent=2)}

Pick the agent whose recommendation best serves the company goal. Consider budget, risk, and deadline together.

Respond ONLY in this exact JSON format, nothing else:
{{
    "winner": "agent_name",
    "decision": "what should be done",
    "reasoning": "why this agent won over others",
    "tradeoffs": "what we are sacrificing by not picking the others"
}}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        return json.loads(text.strip())

    except Exception as e:
        return {
            "winner": "unknown",
            "decision": "arbitration failed",
            "reasoning": str(e),
            "tradeoffs": "none"
        }