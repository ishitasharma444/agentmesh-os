import json


def run(shared_state: dict, custom_input: str = None) -> dict:
    """
    Runs Risk Agent using current AgentMesh shared state.
    Returns structured JSON for conflict detection and frontend.
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
    current_plan = shared_state.get(
        "current_plan",
        "not generated"
    )

    description = f"""
You are the Risk Agent working inside AgentMesh OS.

SHARED ORGANIZATIONAL STATE:

Company Goal: {goal}
Current Route: {route}
Known Route Risk: {route_risk}
Warehouse Status: {warehouse}
Units to Deliver: {units}
Deadline: {deadline}
Total Budget: {budget}
Current Plan: {current_plan}

Additional User Instruction:
{custom_input or "No additional instruction"}

Analyze all operational, route, warehouse, resource,
capacity and delivery risks.

You must:
1. Assign an overall risk level.
2. Evaluate the selected route.
3. Identify possible delays and disruptions.
4. Identify warehouse or capacity risks.
5. Suggest mitigation actions.
6. Provide a risk score from 0 to 100.
7. Give a confidence score from 0.0 to 1.0.
8. Give a clear recommendation.

Respond ONLY in valid JSON using this exact structure:

{{
    "agent": "risk",
    "recommendation": "risk-focused recommendation",
    "confidence": 0.0,
    "reasoning": "detailed risk reasoning",
    "overall_risk_level": "low",
    "route_risk_update": "low",
    "identified_risks": [],
    "mitigation_actions": [],
    "risk_score": 0
}}
"""

    dynamic_task = Task(
        description=description,
        expected_output="Valid JSON risk analysis",
        agent=risk_agent
    )

    crew = Crew(
        agents=[risk_agent],
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
        parsed_output["agent"] = "risk"
        return parsed_output

    except (json.JSONDecodeError, TypeError):
        return {
            "agent": "risk",
            "recommendation": raw_output[:300],
            "confidence": 0.5,
            "reasoning": (
                "Risk Agent returned an output that "
                "could not be parsed as JSON."
            ),
            "overall_risk_level": "unknown",
            "route_risk_update": "unknown",
            "identified_risks": [
                "Risk output parsing failed"
            ],
            "mitigation_actions": [
                "Request manual risk review"
            ],
            "risk_score": 50
        }