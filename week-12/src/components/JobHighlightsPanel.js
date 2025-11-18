import { useState } from "react";
import apiClient from "../api/apiClient";
import { toastService } from "../services/toastService";

export function JobHighlightsPanel() {
  const [jobId, setJobId] = useState("");
  const [summary, setSummary] = useState("");
  const [tags, setTags] = useState("");
  const [highlights, setHighlights] = useState([]);
  const [batchSize, setBatchSize] = useState(200);
  const [loading, setLoading] = useState(false);

  const create = async () => {
    setLoading(true);
    try {
      const payload = {
        job_id: jobId,
        summary,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      };
      const result = await apiClient.createHighlight(payload);
      setHighlights((current) => [...current, result]);
      toastService.success("Highlight created");
      setJobId("");
      setSummary("");
      setTags("");
    } catch (error) {
      toastService.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  const loadHighlights = async () => {
    if (!jobId) {
      toastService.info("Enter job IDs (comma separated) in Job ID field");
      return;
    }
    try {
      const ids = jobId.split(",").map((id) => id.trim());
      const result = await apiClient.getHighlights(ids);
      setHighlights(result.highlights || []);
    } catch (error) {
      toastService.error(error.message);
    }
  };

  const backfill = async () => {
    setLoading(true);
    try {
      await apiClient.triggerHighlightBackfill(batchSize);
      toastService.success("Backfill scheduled");
    } catch (error) {
      toastService.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="card">
      <header>
        <h2>Job Highlights</h2>
        <p className="muted">Create, inspect, and backfill highlight metadata.</p>
      </header>

      <div className="form-grid">
        <label className="field">
          <span>Job ID(s)</span>
          <input value={jobId} onChange={(e) => setJobId(e.target.value)} />
        </label>
        <label className="field">
          <span>Summary</span>
          <input value={summary} onChange={(e) => setSummary(e.target.value)} />
        </label>
        <label className="field">
          <span>Tags (comma separated)</span>
          <input value={tags} onChange={(e) => setTags(e.target.value)} />
        </label>
      </div>

      <div className="actions">
        <button onClick={create} disabled={loading || !jobId || !summary}>
          Create Highlight
        </button>
        <button className="secondary" onClick={loadHighlights}>
          Fetch Highlights
        </button>
      </div>

      <div className="actions">
        <label className="field">
          <span>Backfill batch size</span>
          <input
            type="number"
            min="50"
            step="50"
            value={batchSize}
            onChange={(e) => setBatchSize(Number(e.target.value))}
          />
        </label>
        <button onClick={backfill} disabled={loading}>
          Schedule Backfill
        </button>
      </div>

      {highlights.length > 0 && (
        <div className="status-block">
          <h4>Highlights</h4>
          {highlights.map((highlight) => (
            <article key={highlight.job_id} className="highlight-card">
              <div>
                <strong>Job #{highlight.job_id}</strong>
              </div>
              <p>{highlight.summary}</p>
              <small>Tags: {highlight.tags?.join(", ") || "—"}</small>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

