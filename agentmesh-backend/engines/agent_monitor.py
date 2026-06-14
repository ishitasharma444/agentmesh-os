import google.generativeai as genai
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")


class AgentMonitor:
    """
    AgentMesh Agent Monitor — tracks every agent's health, activity, and ROI.
    Solves Agent Sprawl problem — you always know who is working, who is idle,
    who is doing duplicate work.
    """

    def __init__(self):
        self.registry = {}  # stores all agent metadata

    def register_agent(self, agent_name: str):
        """Called once when agent is first seen — adds it to the registry."""
        if agent_name not in self.registry:
            self.registry[agent_name] = {
                "name": agent_name,
                "status": "idle",           # idle | active | failed
                "first_seen": datetime.now().isoformat(),
                "last_run": None,
                "last_success": None,
                "total_runs": 0,
                "total_failures": 0,
                "idle_since": datetime.now().isoformat(),
                "roi_score": 100,           # starts at 100, drops with failures/idle
                "last_output_summary": None,
            }

    def mark_active(self, agent_name: str):
        """Agent started running."""
        self.register_agent(agent_name)
        self.registry[agent_name]["status"] = "active"
        self.registry[agent_name]["last_run"] = datetime.now().isoformat()
        self.registry[agent_name]["total_runs"] += 1
        self.registry[agent_name]["idle_since"] = None

    def mark_success(self, agent_name: str, output_summary: str):
        """Agent finished successfully."""
        if agent_name in self.registry:
            self.registry[agent_name]["status"] = "idle"
            self.registry[agent_name]["last_success"] = datetime.now().isoformat()
            self.registry[agent_name]["last_output_summary"] = output_summary
            self.registry[agent_name]["idle_since"] = datetime.now().isoformat()
            self._recalculate_roi(agent_name)

    def mark_failed(self, agent_name: str, reason: str):
        """Agent failed or was blocked by circuit breaker."""
        if agent_name in self.registry:
            self.registry[agent_name]["status"] = "failed"
            self.registry[agent_name]["total_failures"] += 1
            self.registry[agent_name]["last_output_summary"] = f"FAILED: {reason}"
            self.registry[agent_name]["idle_since"] = datetime.now().isoformat()
            self._recalculate_roi(agent_name)

    def _recalculate_roi(self, agent_name: str):
        """
        ROI score = how useful is this agent?
        Drops when agent fails too much or stays idle too long.
        """
        agent = self.registry[agent_name]
        total = agent["total_runs"]
        failures = agent["total_failures"]

        if total == 0:
            agent["roi_score"] = 100
            return

        success_rate = ((total - failures) / total) * 100

        # Penalty for idle time
        idle_penalty = 0
        if agent["idle_since"]:
            idle_minutes = (
                datetime.now() -
                datetime.fromisoformat(agent["idle_since"])
            ).seconds / 60
            idle_penalty = min(20, idle_minutes * 2)  # max 20 point penalty

        agent["roi_score"] = round(max(0, success_rate - idle_penalty), 1)

    def get_idle_time_minutes(self, agent_name: str) -> float:
        """Returns how long agent has been idle in minutes."""
        agent = self.registry.get(agent_name)
        if not agent or not agent["idle_since"]:
            return 0
        delta = datetime.now() - datetime.fromisoformat(agent["idle_since"])
        return round(delta.seconds / 60, 1)

    def detect_similar_agents(self, agent_outputs: dict) -> dict:
        """
        AgentMesh Similarity Detector — checks if multiple agents are
        recommending the same thing (duplicate work = wasted resources).
        Uses Gemini to understand semantic similarity, not just string match.
        """

        if len(agent_outputs) < 2:
            return {
                "similar_pairs": [],
                "similarity_detected": False,
                "summary": "Not enough agents to compare"
            }

        summaries = {
            name: data["output"].get("recommendation", "")
            for name, data in agent_outputs.items()
        }

        prompt = f"""
You are the AgentMesh Similarity Detector. Check if any AI agents are doing duplicate work by recommending essentially the same thing.

AGENT RECOMMENDATIONS:
{json.dumps(summaries, indent=2)}

Two agents are "similar" if their recommendations are semantically the same — even if worded differently.
Example: "Take Route A" and "Use the northern highway route" are similar if Route A = northern highway.

Respond ONLY in this exact JSON format, nothing else:
{{
    "similarity_detected": true or false,
    "similar_pairs": [
        {{
            "agents": ["agent1", "agent2"],
            "similarity_score": 0.0 to 1.0,
            "reason": "both are recommending the same route"
        }}
    ],
    "summary": "one line overall summary"
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
                "similar_pairs": [],
                "similarity_detected": False,
                "summary": f"Similarity detection error: {str(e)}"
            }

    def get_all_agent_health(self) -> list:
        """
        Returns full health report of all agents.
        This is what the dashboard Agent Health table shows.
        """
        health_report = []

        for name, data in self.registry.items():
            health_report.append({
                "name": name,
                "status": data["status"],
                "total_runs": data["total_runs"],
                "total_failures": data["total_failures"],
                "roi_score": data["roi_score"],
                "idle_minutes": self.get_idle_time_minutes(name),
                "last_run": data["last_run"],
                "last_success": data["last_success"],
                "last_output_summary": data["last_output_summary"],
                "first_seen": data["first_seen"],
            })

        return health_report

    def get_sprawl_warnings(self) -> list:
        """
        Returns list of warnings about agent sprawl:
        - agents idle too long
        - agents with very low ROI
        - duplicate agents detected
        """
        warnings = []

        for name, data in self.registry.items():
            idle_mins = self.get_idle_time_minutes(name)

            # Idle too long
            if idle_mins > 30:
                warnings.append({
                    "type": "idle_too_long",
                    "agent": name,
                    "message": f"{name} has been idle for {idle_mins} minutes",
                    "severity": "warning"
                })

            # ROI too low
            if data["roi_score"] < 40:
                warnings.append({
                    "type": "low_roi",
                    "agent": name,
                    "message": f"{name} ROI score is {data['roi_score']} — consider replacing",
                    "severity": "critical"
                })

        return warnings


# Singleton — import this everywhere
agent_monitor = AgentMonitor()