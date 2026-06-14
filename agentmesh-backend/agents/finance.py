import json


def run(shared_state: dict, custom_input: str | None = None) -> dict:
    goal = shared_state.get(
        "company_goal",
        "Deliver shipment within budget"
    )
    budget = shared_state.get("budget", 200000)
    budget_used = shared_state.get("budget_used", 0)
    route = shared_state.get("route", "not selected")
    route_risk = shared_state.get("route_risk", "unknown")
    deadline = shared_state.get("deadline", "Friday")
    units = shared_state.get("units_to_deliver", 500)

    task_description = f"""
You are the Finance Agent operating inside AgentMesh OS.

SHARED ORGANIZATIONAL STATE:
Company Goal: {goal}
Total Budget: {budget}
Budget Used: {budget_used}
Remaining Budget: {budget - budget_used}
Selected Route: {route}
Route Risk: {route_risk}
Deadline: {deadline}
Units: {units}

User Instruction:
{custom_input or "No additional instruction"}

Analyze the financial feasibility of the current logistics plan.

Respond ONLY in valid JSON:

{{
    "agent": "finance",
    "recommendation": "short financial recommendation",
    "confidence": 0.0,
    "reasoning": "financial reasoning",
    "estimated_cost": 0,
    "transportation_cost": 0,
    "warehouse_cost": 0,
    "budget_compliance": true,
    "financial_risks": [],
    "cost_efficiency_score": 0
}}
"""

    dynamic_task = Task(
        description=task_description,
        expected_output="Valid JSON financial analysis",
        agent=finance_agent
    )

    crew = Crew(
        agents=[finance_agent],
        tasks=[dynamic_task],
        verbose=False
    )

    result = crew.kickoff()
    raw = str(result).strip()

    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip().rstrip("```").strip()

    try:
        parsed = json.loads(raw)
        parsed["agent"] = "finance"
        return parsed

    except Exception:
        return {
            "agent": "finance",
            "recommendation": raw[:300],
            "confidence": 0.5,
            "reasoning": "Finance output could not be parsed as JSON",
            "estimated_cost": 0,
            "transportation_cost": 0,
            "warehouse_cost": 0,
            "budget_compliance": True,
            "financial_risks": [],
            "cost_efficiency_score": 50
        }