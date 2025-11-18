import { useEffect, useState } from "react";
import apiClient from "../api/apiClient";
import { toastService } from "../services/toastService";

const SUGGESTED_TAGS = [
  "Remote",
  "Hybrid",
  "Senior",
  "Contract",
  "Growth",
  "AI",
  "Data",
  "Security",
];

export function JobTagsPanel() {
  const [tags, setTags] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [rolloutStatus, setRolloutStatus] = useState(null);

  useEffect(() => {
    let mounted = true;
    apiClient
      .getJobTags()
      .then((data) => {
        if (!mounted) return;
        const preferred = data.tags || [];
        setTags(preferred);
        setSelected(new Set(preferred));
      })
      .catch(() => toastService.error("Failed to fetch tags"));
    return () => {
      mounted = false;
    };
  }, []);

  const toggleTag = (tag) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(tag)) {
        next.delete(tag);
      } else if (next.size < 6) {
        next.add(tag);
      } else {
        toastService.info("You can track up to 6 tags");
      }
      return next;
    });
  };

  const save = async () => {
    setLoading(true);
    try {
      await apiClient.updateJobTags(Array.from(selected));
      setTags(Array.from(selected));
      toastService.success("Preferences saved");
    } catch (error) {
      toastService.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  const rollout = async () => {
    setLoading(true);
    try {
      const response = await apiClient.triggerJobTagRollout();
      setRolloutStatus(response);
      toastService.success("Rollout triggered");
    } catch (error) {
      toastService.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="card">
      <header>
        <h2>Job Tags</h2>
        <p className="muted">
          Curate tags to personalize job discovery for every user.
        </p>
      </header>

      <div className="tag-grid">
        {SUGGESTED_TAGS.map((tag) => (
          <button
            key={tag}
            className={`tag-chip ${selected.has(tag) ? "tag-chip--active" : ""}`}
            onClick={() => toggleTag(tag)}
          >
            {tag}
          </button>
        ))}
      </div>

      <div className="actions">
        <button onClick={save} disabled={loading}>
          Save Preferences
        </button>
        <button className="secondary" onClick={rollout} disabled={loading}>
          Trigger Full Rollout
        </button>
      </div>

      {rolloutStatus && (
        <pre className="status-block">
          {JSON.stringify(rolloutStatus, null, 2)}
        </pre>
      )}

      {tags.length > 0 && (
        <div className="current-tags">
          <strong>Current:</strong> {tags.join(", ")}
        </div>
      )}
    </section>
  );
}

