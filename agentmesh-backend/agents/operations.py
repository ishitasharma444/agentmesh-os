import json


def run(shared_state: dict, custom_input: str = None) -> dict:
    """
    Runs Operations/Transportation Agent using the latest state.
    Returns a structured execution plan.
    """

    goal = shared_state.get(
        "company_goal",
        "Complete delivery safely within budget"
    )
    route = shared_state.get("route", "not selected")
    route_risk = shared_state.get(
        "route_risk",
        "unknown"
    )
    warehouse = shared_state.get(
        "warehouse_status",
        "unknown"
    )
    deadline = shared_state.get("deadline", "Friday")
    units = shared_state.get("units_to_deliver", 500)
    budget = shared_state.get("budget", 200000)
    budget_used = shared_state.get("budget_used", 0)
    current_plan = shared_state.get(
        "current_plan",
        "not generated"
    )

    description = f"""
You are the Operations Agent working inside AgentMesh OS.

SHARED ORGANIZATIONAL STATE:

Company Goal: {goal}
Selected Route: {route}
Route Risk: {route_risk}
Warehouse: {warehouse}
Units to Deliver: {units}
Deadline: {deadline}
Total Budget: {budget}
Budget Used: {budget_used}
Remaining Budget: {budget - budget_used}
Current Plan: {current_plan}

Additional User Instruction:
{custom_input or "No additional instruction"}

Create an executable transportation and resource plan.

You must:
1. Select the transportation mode.
2. Select the appropriate vehicle type.
3. Calculate the number of vehicles required.
4. Estimate capacity utilization.
5. Create dispatch and arrival timings.
6. Provide a resource allocation plan.
7. Indicate operational readiness.
8. Give a confidence score from 0.0 to 1.0.
9. Give a final operations recommendation.

Respond ONLY in valid JSON using this exact structure:

{{
    "agent": "operations",
    "recommendation": "execution recommendation",
    "confidence": 0.0,
    "reasoning": "operations reasoning",
    "transport_mode": "road",
    "vehicle_type": "truck type",
    "vehicles_required": 0,
    "capacity_utilization": 0,
    "execution_timeline": {{
        "dispatch": "time",
        "arrival": "time"
    }},
    "resource_plan": [],
    "operational_status": "ready"
}}
"""

    dynamic_task = Task(
        description=description,
        expected_output="Valid JSON operations plan",
        agent=transport_agent
    )

    crew = Crew(
        agents=[transport_agent],
        tasks=[dynamic_task],
        verbose=False
    )

    result = crew.kickoff()
    raw_output = str(result).strip()

    if "```" in raw_output:
        raw_output = raw_output.split("```")[1]

        if raw_output.startswith("json"):
            raw_output = raw_output[4:]

        raw_output = (
            raw_output
            .strip()
            .rstrip("```")
            .strip()
        )

    try:
        parsed_output = json.loads(raw_output)
        parsed_output["agent"] = "operations"
        return parsed_output

    except (json.JSONDecodeError, TypeError):
        return {
            "agent": "operations",
            "recommendation": raw_output[:300],
            "confidence": 0.5,
            "reasoning": (
                "Operations Agent returned an output "
                "that could not be parsed as JSON."
            ),
            "transport_mode": "unknown",
            "vehicle_type": "unknown",
            "vehicles_required": 0,
            "capacity_utilization": 0,
            "execution_timeline": {
                "dispatch": "unknown",
                "arrival": "unknown"
            },
            "resource_plan": [],
            "operational_status": "review"
        }