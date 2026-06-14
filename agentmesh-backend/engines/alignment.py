import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

def score_alignment(agent_name: str, agent_action: dict, shared_state: dict) -> dict:
    """
    AgentMesh Alignment Engine — runs AFTER state update.
    Scores every agent action against the company goal (0-100).
    If score drops below 60 → alert → dashboard shows drift warning.
    """

    prompt = f"""
You are the AgentMesh Alignment Engine. Your job is to score how well an agent's action aligns with the company's goal.

COMPANY GOAL: {shared_state.get('company_goal')}
DEADLINE: {shared_state.get('deadline')}
TOTAL BUDGET: {shared_state.get('budget')}
BUDGET USED SO FAR: {shared_state.get('budget_used')}
CURRENT ROUTE RISK: {shared_state.get('route_risk')}
UNITS TO DELIVER: {shared_state.get('units_to_deliver')}

AGENT: {agent_name}
AGENT ACTION: {json.dumps(agent_action)}

Score this action from 0 to 100 based on:
- 0-40: Actively hurts the company goal
- 41-60: Neutral or minor help
- 61-80: Good alignment
- 81-100: Directly serves the company goal

Respond ONLY in this exact JSON format, nothing else:
{{
    "score": 0 to 100,
    "label": "Critical Drift" or "Warning" or "Aligned" or "Strongly Aligned",
    "reason": "one line explanation of the score"
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

        # If score drops below 60 — add alert to shared state
        # This is how dashboard knows to show drift warning
        if result["score"] < 60:
            from shared_state import shared_state as state_instance
            state_instance.add_alert(
                message=f"{agent_name} alignment dropped to {result['score']} — {result['reason']}",
                severity="critical" if result["score"] < 40 else "warning"
            )

        return result

    except Exception as e:
        return {
            "score": 50,
            "label": "Warning",
            "reason": f"Alignment scoring error: {str(e)}"
        }


def calculate_overall_alignment(all_scores: list) -> float:
    """
    Takes all individual agent alignment scores and returns one overall score.
    This is the big number shown on the dashboard gauge.
    """
    if not all_scores:
        return 100.0
    return round(sum(all_scores) / len(all_scores), 1)