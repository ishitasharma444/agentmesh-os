from datetime import datetime

class SharedState:
    def __init__(self):
        self.state = {
            "company_goal": "Deliver 500 units to Mumbai by Friday within 2L budget",
            "budget": 200000,
            "budget_used": 0,
            "route": None,
            "route_risk": "unknown",
            "warehouse_status": "available",
            "deadline": "Friday",
            "units_to_deliver": 500,
            "current_plan": None,
            "alerts": [],
            "alignment_score": 100,
        }
        self.history = []
        self.agent_outputs = {}      # AgentMesh stores every agent's last output
        self.conflict_log = []       # AgentMesh logs every conflict + resolution
        self.circuit_breaker_log = []  # AgentMesh logs every blocked output

    def get(self):
        return self.state.copy()

    def update(self, key, value, updated_by):
        # AgentMesh records who changed what and when — full audit trail
        old_value = self.state.get(key)
        self.state[key] = value
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "updated_by": updated_by,
            "key": key,
            "old_value": old_value,
            "new_value": value,
        })

    def add_alert(self, message, severity="warning"):
        self.state["alerts"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "severity": severity,
        })

    def store_agent_output(self, agent_name, output):
        # AgentMesh stores output BEFORE circuit breaker decides to pass or block
        self.agent_outputs[agent_name] = {
            "output": output,
            "timestamp": datetime.now().isoformat()
        }

    def log_circuit_breaker(self, agent_name, output, reason, blocked=True):
        self.circuit_breaker_log.append({
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "blocked": blocked,
            "reason": reason,
            "output": output,
        })

    def log_conflict(self, agents_involved, winner, reasoning):
        self.conflict_log.append({
            "timestamp": datetime.now().isoformat(),
            "agents_involved": agents_involved,
            "winner": winner,
            "reasoning": reasoning,
        })

    def get_history(self):
        return self.history

    def get_all_agent_outputs(self):
        return self.agent_outputs


# Singleton — import this everywhere, never create new SharedState()
shared_state = SharedState()