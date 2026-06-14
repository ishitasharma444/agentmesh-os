import os
import json
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

def cost_optimizer_agent(shared_state: dict) -> dict:
    """
    AgentMesh Cost Optimizer Agent.
    Intentionally similar to finance agent — will trigger similarity alert
    in AgentMesh Agent Monitor (both analyze cost for same scenario).
    """

    prompt = f"""
You are a Cost Optimization Analyst AI agent working inside AgentMesh OS.

Your job: Analyze the logistics scenario and recommend the most cost-effective option.

CURRENT SHARED STATE:
- Company Goal: {shared_state.get('company_goal')}
- Total Budget: ₹{shared_state.get('budget')}
- Budget Used: ₹{shared_state.get('budget_used')}
- Route Risk: {shared_state.get('route_risk')}
- Units to Deliver: {shared_state.get('units_to_deliver')}
- Deadline: {shared_state.get('deadline')}
- Current Plan: {shared_state.get('current_plan')}

Focus purely on cost minimization. Suggest cheapest viable delivery option.
Consider: route cost, fuel, warehouse fees, truck rental.
Estimate total cost and how much budget remains.

Respond ONLY in this exact JSON format, nothing else:
{{
    "agent": "cost_optimizer",
    "recommendation": "specific cost-focused recommendation",
    "confidence": 0.0 to 1.0,
    "reasoning": "cost breakdown and why this is cheapest",
    "estimated_cost": number in rupees,
    "cost_savings": "how much saved vs alternatives",
    "budget_remaining": number in rupees
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
        result["agent"] = "cost_optimizer"
        return result

    except Exception as e:
        return {
            "agent": "cost_optimizer",
            "recommendation": "Use Route B for lowest cost delivery — saves ₹35,000 vs Route A",
            "confidence": 0.65,
            "reasoning": f"Cost analysis: Route B is cheapest option available. Error: {str(e)}",
            "estimated_cost": 165000,
            "cost_savings": "₹35,000 vs Route A",
            "budget_remaining": 35000
        }