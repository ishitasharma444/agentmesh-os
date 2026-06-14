from dotenv import load_dotenv
load_dotenv()

from crewai import LLM, Agent, Task, Crew
import json

llm = LLM(
    model="gemini/gemini-2.0-flash",
    temperature=0.7
)

logistic_agent = Agent(
    role="Logistics Operations Manager",
    goal="Plan the most efficient, safe, and cost-effective shipment route and warehouse strategy",
    backstory="""The Logistics Agent acts as a Senior Logistics Operations Manager within the AgentMesh OS ecosystem.
        It creates optimized shipment plans, selects routes and warehouses, allocates resources, detects risks,
        and collaborates with other agents. It provides confidence scores and explainable decisions for every recommendation.""",
    verbose=False,
    llm=llm
)


def run(shared_state: dict, custom_input: str = None) -> dict:
    """
    AgentMesh-compatible runner.
    Reads from SharedState, runs CrewAI agent, returns structured output.
    """
    goal = shared_state.get("company_goal", "Deliver units within budget")
    budget = shared_state.get("budget", 200000)
    budget_used = shared_state.get("budget_used", 0)
    units = shared_state.get("units_to_deliver", 500)
    deadline = shared_state.get("deadline", "Friday")
    route_risk = shared_state.get("route_risk", "unknown")
    warehouse = shared_state.get("warehouse_status", "available")

    base_description = f"""
You are operating inside AgentMesh OS. The shared system state is:
- Company Goal: {goal}
- Total Budget: â‚¹{budget}
- Budget Already Used: â‚¹{budget_used}
- Available Budget: â‚¹{budget - budget_used}
- Units to Deliver: {units}
- Deadline: {deadline}
- Current Route Risk: {route_risk}
- Warehouse Status: {warehouse}

{"User Command: " + custom_input if custom_input else ""}

Your task:
1. Select the best warehouse for dispatch
2. Select the safest and most efficient route to Mumbai
3. Estimate delivery time (ETA)
4. Recommend number of vehicles needed
5. Flag any risks you detect
6. Give a confidence score (0.0 to 1.0) for your plan

Respond ONLY in this exact JSON format, nothing else:
{{
    "agent": "logistics",
    "recommendation": "short summary of your plan",
    "confidence": 0.85,
    "reasoning": "detailed explanation of your decisions",
    "warehouse_selected": "warehouse name",
    "route_selected": "route description",
    "eta": "estimated time of arrival",
    "vehicles_required": 5,
    "risks_detected": ["risk1", "risk2"]
}}
"""

    task = Task(
        description=base_description,
        agent=logistic_agent,
        expected_output="JSON with agent, recommendation, confidence, reasoning, warehouse_selected, route_selected, eta, vehicles_required, risks_detected"
    )

    crew = Crew(
        agents=[logistic_agent],
        tasks=[task],
        verbose=False
    )

    result = crew.kickoff()
    raw = str(result).strip()

    # Clean markdown if Gemini adds it
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip().rstrip("```").strip()

    try:
        return json.loads(raw)
    except Exception:
        return {
            "agent": "logistics",
            "recommendation": raw[:300],
            "confidence": 0.5,
            "reasoning": "Raw output â€” JSON parse failed",
            "warehouse_selected": "unknown",
            "route_selected": "unknown",
            "eta": "unknown",
            "vehicles_required": 0,
            "risks_detected": []
        }