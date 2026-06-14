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
    AgentMesh Arbitration Engine — picks winner + gives confidence score + full reasoning.
    Confidence = how sure is the system about this decision.
    """

    # Calculate individual agent confidences first
    agent_confidences = {
        name: data["output"].get("confidence", 0.5)
        for name, data in agent_outputs.items()
    }

    prompt = f"""
You are the AgentMesh Arbitration Engine. Multiple AI agents disagree. You must pick a winner based on the company goal and assign a confidence score to your decision.

COMPANY GOAL: {shared_state.get('company_goal')}
BUDGET: {shared_state.get('budget')}
BUDGET USED: {shared_state.get('budget_used')}
ROUTE RISK: {shared_state.get('route_risk')}

ALL AGENT OUTPUTS WITH THEIR CONFIDENCE SCORES:
{json.dumps({name: {
    "output": data["output"],
    "agent_confidence": agent_confidences[name]
} for name, data in agent_outputs.items()}, indent=2)}

Pick the agent whose recommendation best serves the company goal.
Also give YOUR confidence in this arbitration decision (0.0 to 1.0):
- High confidence (>0.8) = clear winner, strong reasoning
- Medium confidence (0.5-0.8) = winner exists but tradeoffs are significant  
- Low confidence (<0.5) = very hard call, could go either way

Respond ONLY in this exact JSON format, nothing else:
{{
    "winner": "agent_name",
    "decision": "what should be done",
    "reasoning": "why this agent won over others",
    "tradeoffs": "what we are sacrificing by not picking the others",
    "arbitration_confidence": 0.0 to 1.0,
    "confidence_explanation": "why you are this confident in the arbitration decision",
    "agent_confidence_summary": {{
        "highest_confidence_agent": "agent_name",
        "lowest_confidence_agent": "agent_name",
        "average_confidence": 0.0 to 1.0
    }}
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

        # Add raw agent confidences to result for dashboard
        result["individual_agent_confidences"] = agent_confidences

        return result

    except Exception as e:
        return {
            "winner": "unknown",
            "decision": "arbitration failed",
            "reasoning": str(e),
            "tradeoffs": "none",
            "arbitration_confidence": 0.0,
            "confidence_explanation": "arbitration engine error",
            "agent_confidence_summary": {},
            "individual_agent_confidences": agent_confidences
        }