import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

def validate_output(agent_name: str, agent_output: dict, shared_state: dict) -> dict:
    """
    AgentMesh Circuit Breaker — runs BEFORE state update.
    Checks if agent output is consistent with current shared state.
    If invalid → blocks it, logs it, does NOT update state.
    """

    prompt = f"""
You are the AgentMesh Circuit Breaker. Your job is to validate an AI agent's output before it updates the shared system state.

COMPANY GOAL: {shared_state.get('company_goal')}
CURRENT BUDGET: {shared_state.get('budget')}
BUDGET USED: {shared_state.get('budget_used')}
CURRENT ROUTE RISK: {shared_state.get('route_risk')}
CURRENT PLAN: {shared_state.get('current_plan')}

AGENT: {agent_name}
AGENT OUTPUT: {json.dumps(agent_output)}

Validate this output. Check:
1. Does it contradict the company goal?
2. Does it exceed the budget?
3. Does it ignore a known high risk already in shared state?
4. Is the confidence too low (below 0.4)?

Respond ONLY in this exact JSON format, nothing else:
{{
    "valid": true or false,
    "confidence": 0.0 to 1.0,
    "reason": "one line explanation"
}}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Clean up response if Gemini adds markdown
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        result = json.loads(text.strip())
        return result

    except Exception as e:
        # If Gemini fails, default to blocking — safety first
        return {
            "valid": False,
            "confidence": 0.0,
            "reason": f"Circuit breaker error — defaulting to block: {str(e)}"
        }