const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(
    `${API_BASE_URL}${path}`,
    {
      ...options,

      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    }
  );

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    try {
      const errorData = await response.json();

      if (typeof errorData.detail === "string") {
        message = errorData.detail;
      } else if (errorData.detail) {
        message = JSON.stringify(errorData.detail);
      }
    } catch {
      message = response.statusText || message;
    }

    throw new Error(message);
  }

  return response.json();
}

export const agentMeshApi = {
  getHealth() {
    return request("/health");
  },

  getDashboard() {
    return request("/dashboard");
  },

  getState() {
    return request("/state");
  },

  getAgentHealth() {
    return request("/agent-health");
  },

  getAgentOutputs() {
    return request("/agent-outputs");
  },

  getConflicts() {
    return request("/conflicts");
  },

  getSimilarity() {
    return request("/similarity");
  },

  runPipeline() {
    return request("/run", {
      method: "POST",
    });
  },

  runAgent(agentName) {
    return request(
      `/run/${encodeURIComponent(agentName)}`,
      {
        method: "POST",
      }
    );
  },
};

export { API_BASE_URL };