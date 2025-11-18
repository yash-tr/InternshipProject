import { useMemo, useState } from "react";
import apiClient from "../api/apiClient";
import { toastService } from "../services/toastService";

const SAMPLE_JOB_IDS = ["101", "205", "899", "330", "407"];

export function ClickOptimizationPanel() {
  const [rankedIds, setRankedIds] = useState([]);
  const [context, setContext] = useState("dashboard");
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState(null);

  const payload = useMemo(
    () => ({
      job_ids: SAMPLE_JOB_IDS,
      context,
    }),
    [context]
  );

  const optimize = async () => {
    setLoading(true);
    try {
      const result = await apiClient.rankJobs(payload.job_ids, payload.context);
      setRankedIds(result.job_ids);
      setToken(result.impression_token);
      toastService.success("Ranking refreshed");
    } catch (error) {
      toastService.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="card">
      <header>
        <h2>Click Optimization</h2>
        <p className="muted">
          Test the new backend service and inspect impression tokens.
        </p>
      </header>

      <label className="field">
        <span>Context</span>
        <select value={context} onChange={(e) => setContext(e.target.value)}>
          <option value="dashboard">Dashboard</option>
          <option value="search">Search</option>
          <option value="alert">Alert</option>
        </select>
      </label>

      <button onClick={optimize} disabled={loading}>
        {loading ? "Optimizing..." : "Run Ranking"}
      </button>

      {rankedIds.length > 0 && (
        <div className="status-block">
          <div>
            <strong>Impression Token:</strong> {token}
          </div>
          <ol>
            {rankedIds.map((id) => (
              <li key={id}>{id}</li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

