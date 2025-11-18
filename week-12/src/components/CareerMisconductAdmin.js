import { useEffect, useState } from "react";
import apiClient from "../api/apiClient";
import { toastService } from "../services/toastService";

export function CareerMisconductAdmin() {
  const [policy, setPolicy] = useState(null);
  const [blocks, setBlocks] = useState([]);
  const [form, setForm] = useState({
    target_id: "",
    reason: "",
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    refresh();
  }, []);

  const refresh = () => {
    apiClient
      .fetchMisconductSummary()
      .then((res) => {
        setPolicy(res.policy);
        setBlocks(res.blocks || []);
      })
      .catch((err) => toastService.error(err.message));
  };

  const handleBlock = async () => {
    setLoading(true);
    try {
      await apiClient.blockUser(form);
      toastService.success("User blocked");
      setForm({ target_id: "", reason: "" });
      refresh();
    } catch (error) {
      toastService.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUnblock = async (target_id) => {
    setLoading(true);
    try {
      await apiClient.unblockUser({ target_id });
      toastService.success("User unblocked");
      refresh();
    } catch (error) {
      toastService.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="card">
      <header>
        <h2>Career Misconduct Enforcement</h2>
        <p className="muted">
          Apply policy-driven blocks and audit enforcement actions.
        </p>
      </header>

      {policy && (
        <details className="policy-details" open>
          <summary>Policy v{policy.version}</summary>
          <ul>
            {policy.rules.map((rule) => (
              <li key={rule.id}>
                <strong>{rule.id}</strong>: {rule.description} →{" "}
                <em>{rule.action}</em>
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className="form-grid">
        <label className="field">
          <span>Target User ID</span>
          <input
            value={form.target_id}
            onChange={(e) => setForm((f) => ({ ...f, target_id: e.target.value }))}
          />
        </label>
        <label className="field">
          <span>Reason</span>
          <input
            value={form.reason}
            onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))}
          />
        </label>
      </div>

      <button onClick={handleBlock} disabled={loading || !form.target_id}>
        Block User
      </button>

      <div className="status-block">
        <h4>Active Blocks</h4>
        {blocks.length === 0 ? (
          <p className="muted">No active blocks.</p>
        ) : (
          <ul className="block-list">
            {blocks.map((block) => (
              <li key={block.id}>
                <div>
                  <strong>User #{block.user_id}</strong> — {block.reason}
                </div>
                <button
                  className="secondary"
                  onClick={() => handleUnblock(block.user_id)}
                  disabled={loading}
                >
                  Unblock
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

