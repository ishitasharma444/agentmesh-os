import {
  Activity,
  AlertTriangle,
  Bot,
  Boxes,
  BrainCircuit,
  CheckCircle2,
  CircleDollarSign,
  Copy,
  Gauge,
  Network,
  Play,
  RefreshCcw,
  Route,
  ShieldCheck,
  Truck,
  Warehouse,
} from "lucide-react";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { agentMeshApi } from "./services/api";


const agentMetadata = {
  risk: {
    label: "Risk Agent",
    icon: ShieldCheck,
  },

  logistics: {
    label: "Logistics Agent",
    icon: Truck,
  },

  finance: {
    label: "Finance Agent",
    icon: CircleDollarSign,
  },

  cost_optimizer: {
    label: "Cost Optimizer",
    icon: Gauge,
  },

  operations: {
    label: "Operations Agent",
    icon: Boxes,
  },

  supply_checker: {
    label: "Supply Checker",
    icon: Warehouse,
  },
};


function formatAgentName(name) {
  if (agentMetadata[name]) {
    return agentMetadata[name].label;
  }

  return name
    .split("_")
    .map(
      (part) =>
        part.charAt(0).toUpperCase() +
        part.slice(1)
    )
    .join(" ");
}


function formatConfidence(value) {
  const number = Number(value);

  if (Number.isNaN(number)) {
    return 0;
  }

  if (number <= 1) {
    return Math.round(number * 100);
  }

  return Math.round(number);
}


function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  tone = "blue",
}) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <div className="metric-card__icon">
        <Icon size={22} />
      </div>

      <div>
        <p className="metric-card__title">{title}</p>
        <strong className="metric-card__value">
          {value}
        </strong>
        <p className="metric-card__subtitle">
          {subtitle}
        </p>
      </div>
    </article>
  );
}


function AgentCard({ agent, output }) {
  const metadata =
    agentMetadata[agent.name] || {
      label: formatAgentName(agent.name),
      icon: Bot,
    };

  const Icon = metadata.icon;

  const confidence = formatConfidence(
    output?.confidence
  );

  const status =
    agent.status || "idle";

  return (
    <article className="agent-card">
      <div className="agent-card__header">
        <div className="agent-card__identity">
          <span className="agent-card__icon">
            <Icon size={20} />
          </span>

          <div>
            <h3>{metadata.label}</h3>
            <p>{status}</p>
          </div>
        </div>

        <span
          className={`status-pill status-pill--${status}`}
        >
          {status}
        </span>
      </div>

      <div className="confidence">
        <div className="confidence__label">
          <span>Confidence</span>
          <strong>{confidence}%</strong>
        </div>

        <div className="confidence__track">
          <div
            className="confidence__fill"
            style={{
              width: `${confidence}%`,
            }}
          />
        </div>
      </div>

      <p className="agent-card__recommendation">
        {output?.recommendation ||
          agent.last_output_summary ||
          "No output generated yet."}
      </p>

      <div className="agent-card__stats">
        <span>Runs: {agent.total_runs || 0}</span>
        <span>Failures: {agent.total_failures || 0}</span>
        <span>ROI: {agent.roi_score ?? 100}</span>
      </div>
    </article>
  );
}


function App() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [connectionStatus, setConnectionStatus] =
    useState("Checking");


  const loadDashboard = useCallback(async () => {
    try {
      setLoading(true);

      const [healthResponse, dashboardResponse] =
        await Promise.all([
          agentMeshApi.getHealth(),
          agentMeshApi.getDashboard(),
        ]);

      setConnectionStatus(
        healthResponse.status === "healthy"
          ? "Connected"
          : "Warning"
      );

      setDashboard(dashboardResponse);
      setError("");
    } catch (requestError) {
      setConnectionStatus("Disconnected");
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }, []);


  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);


  async function runPipeline() {
    try {
      setRunning(true);
      setError("");

      await agentMeshApi.runPipeline();
      await loadDashboard();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setRunning(false);
    }
  }


  async function runSupplyChecker() {
    try {
      setRunning(true);
      setError("");

      await agentMeshApi.runAgent(
        "supply_checker"
      );

      await loadDashboard();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setRunning(false);
    }
  }


  const stats = dashboard?.stats || {};
  const state = dashboard?.state || {};
  const agents = dashboard?.agents || [];
  const outputs = dashboard?.agent_outputs || {};
  const warnings =
    dashboard?.sprawl_warnings || [];
  const conflicts =
    dashboard?.conflicts || [];


  const pipelineAgents = useMemo(
    () => [
      "risk",
      "logistics",
      "finance",
      "cost_optimizer",
      "operations",
    ],
    []
  );


  if (loading && !dashboard) {
    return (
      <div className="loading-screen">
        <BrainCircuit size={42} />
        <h1>Loading AgentMesh OS</h1>
        <p>Connecting to the intelligence engine...</p>
      </div>
    );
  }


  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__logo">
            <Network size={25} />
          </span>

          <div>
            <h1>AgentMesh OS</h1>
            <p>Intelligence Platform</p>
          </div>
        </div>

        <nav className="sidebar__navigation">
          <a
            className="nav-item nav-item--active"
            href="#overview"
          >
            <Activity size={18} />
            Overview
          </a>

          <a className="nav-item" href="#flow">
            <Route size={18} />
            Agent Flow
          </a>

          <a className="nav-item" href="#oil">
            <BrainCircuit size={18} />
            OIL Layer
          </a>

          <a className="nav-item" href="#agents">
            <Bot size={18} />
            Agent Health
          </a>

          <a className="nav-item" href="#analysis">
            <AlertTriangle size={18} />
            Analysis
          </a>
        </nav>

        <div className="system-status">
          <CheckCircle2 size={19} />

          <div>
            <strong>Backend Status</strong>
            <p>{connectionStatus}</p>
          </div>
        </div>
      </aside>


      <main className="main-content">
        <header className="topbar">
          <div>
            <p className="eyebrow">
              Executive Intelligence Dashboard
            </p>

            <h2>
              Agent Intelligence and Coordination
            </h2>
          </div>

          <div className="topbar__actions">
            <button
              className="button button--secondary"
              onClick={loadDashboard}
              disabled={loading}
            >
              <RefreshCcw size={17} />
              Refresh
            </button>

            <button
              className="button button--primary"
              onClick={runPipeline}
              disabled={running}
            >
              <Play size={17} />

              {running
                ? "Running Pipeline..."
                : "Run AgentMesh"}
            </button>
          </div>
        </header>


        {error && (
          <div className="error-banner">
            <AlertTriangle size={19} />
            <span>{error}</span>
          </div>
        )}


        <section
          className="metrics-grid"
          id="overview"
        >
          <MetricCard
            title="Registered Agents"
            value={stats.registered_agents || 0}
            subtitle="Agents known to AgentMesh"
            icon={Bot}
            tone="blue"
          />

          <MetricCard
            title="System Confidence"
            value={`${stats.system_confidence || 0}%`}
            subtitle="Average agent confidence"
            icon={Gauge}
            tone="green"
          />

          <MetricCard
            title="Conflicts"
            value={stats.conflicts || 0}
            subtitle="Detected agent disagreements"
            icon={AlertTriangle}
            tone="red"
          />

          <MetricCard
            title="Unused Agents"
            value={stats.unused_agents || 0}
            subtitle="Potential agent sprawl"
            icon={Copy}
            tone="orange"
          />
        </section>


        <section className="content-grid">
          <article
            className="panel panel--wide"
            id="flow"
          >
            <div className="panel__header">
              <div>
                <p className="eyebrow">
                  Execution Architecture
                </p>

                <h2>Agent Flow</h2>
              </div>

              <span className="panel__badge">
                Live Pipeline
              </span>
            </div>

            <div className="pipeline">
              {pipelineAgents.map(
                (agentName, index) => {
                  const metadata =
                    agentMetadata[agentName];

                  const Icon =
                    metadata?.icon || Bot;

                  const agent = agents.find(
                    (item) =>
                      item.name === agentName
                  );

                  return (
                    <div
                      className="pipeline__item"
                      key={agentName}
                    >
                      <div className="pipeline__step">
                        <span className="pipeline__icon">
                          <Icon size={21} />
                        </span>

                        <strong>
                          {formatAgentName(agentName)}
                        </strong>

                        <small>
                          {agent?.status || "idle"}
                        </small>
                      </div>

                      {index <
                        pipelineAgents.length - 1 && (
                        <span className="pipeline__arrow">
                          →
                        </span>
                      )}
                    </div>
                  );
                }
              )}

              <div className="pipeline__item">
                <span className="pipeline__arrow">
                  →
                </span>

                <div className="pipeline__step pipeline__step--final">
                  <span className="pipeline__icon">
                    <BrainCircuit size={21} />
                  </span>

                  <strong>Final Decision</strong>
                  <small>AgentMesh Engine</small>
                </div>
              </div>
            </div>
          </article>


          <article className="panel" id="oil">
            <div className="panel__header">
              <div>
                <p className="eyebrow">
                  Shared Intelligence
                </p>

                <h2>OIL Layer</h2>
              </div>

              <BrainCircuit size={22} />
            </div>

            <div className="oil-list">
              <div>
                <span>Organization Goal</span>
                <strong>
                  {state.company_goal || "Not set"}
                </strong>
              </div>

              <div>
                <span>Budget</span>
                <strong>
                  ₹{state.budget || 0}
                </strong>
              </div>

              <div>
                <span>Budget Used</span>
                <strong>
                  ₹{state.budget_used || 0}
                </strong>
              </div>

              <div>
                <span>Route Risk</span>
                <strong>
                  {state.route_risk || "unknown"}
                </strong>
              </div>

              <div>
                <span>Alignment Score</span>
                <strong>
                  {state.alignment_score ?? 100}%
                </strong>
              </div>
            </div>
          </article>


          <article className="panel">
            <div className="panel__header">
              <div>
                <p className="eyebrow">
                  Final Output
                </p>

                <h2>Recommendation</h2>
              </div>

              <Warehouse size={22} />
            </div>

            <div className="recommendation-card">
              <span>Current Plan</span>

              <h3>
                {state.current_plan ||
                  "Run the pipeline to generate a recommendation."}
              </h3>

              <div className="recommendation-meta">
                <span>
                  Route: {state.route || "Pending"}
                </span>

                <span>
                  Warehouse:{" "}
                  {state.warehouse_status ||
                    "Pending"}
                </span>
              </div>
            </div>
          </article>
        </section>


        <section className="section" id="agents">
          <div className="section__header">
            <div>
              <p className="eyebrow">
                Agent Monitoring
              </p>

              <h2>Agent Health and Confidence</h2>
            </div>

            <button
              className="button button--secondary"
              onClick={runSupplyChecker}
              disabled={running}
            >
              <Play size={17} />
              Run Supply Checker
            </button>
          </div>

          <div className="agents-grid">
            {agents.map((agent) => (
              <AgentCard
                key={agent.name}
                agent={agent}
                output={outputs[agent.name]}
              />
            ))}
          </div>
        </section>


        <section
          className="analysis-grid"
          id="analysis"
        >
          <article className="panel">
            <div className="panel__header">
              <div>
                <p className="eyebrow">
                  Agent Sprawl
                </p>

                <h2>Warnings</h2>
              </div>

              <Copy size={22} />
            </div>

            <div className="event-list">
              {warnings.length === 0 ? (
                <p className="empty-state">
                  No agent-sprawl warnings detected.
                </p>
              ) : (
                warnings.map(
                  (warning, index) => (
                    <div
                      className="event-item"
                      key={`${warning.agent}-${index}`}
                    >
                      <AlertTriangle size={18} />

                      <div>
                        <strong>
                          {formatAgentName(
                            warning.agent
                          )}
                        </strong>

                        <p>{warning.message}</p>
                      </div>
                    </div>
                  )
                )
              )}
            </div>
          </article>


          <article className="panel">
            <div className="panel__header">
              <div>
                <p className="eyebrow">
                  Arbitration
                </p>

                <h2>Conflict History</h2>
              </div>

              <ShieldCheck size={22} />
            </div>

            <div className="event-list">
              {conflicts.length === 0 ? (
                <p className="empty-state">
                  No conflict history is available.
                </p>
              ) : (
                conflicts.map(
                  (conflict, index) => (
                    <div
                      className="event-item"
                      key={index}
                    >
                      <AlertTriangle size={18} />

                      <div>
                        <strong>
                          Winner:{" "}
                          {formatAgentName(
                            conflict.winner ||
                              "unknown"
                          )}
                        </strong>

                        <p>
                          {conflict.reasoning ||
                            "No arbitration reasoning available."}
                        </p>
                      </div>
                    </div>
                  )
                )
              )}
            </div>
          </article>
        </section>
      </main>
    </div>
  );
}

export default App;