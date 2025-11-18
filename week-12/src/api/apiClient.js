const API_BASE_URL =
  process.env.REACT_APP_API_URL || "http://localhost:3000/api/v1";

class ApiClient {
  constructor() {
    this.token = localStorage.getItem("auth_token");
  }

  get headers() {
    const headers = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    return headers;
  }

  async request(path, options = {}) {
    const config = {
      ...options,
      headers: {
        ...this.headers,
        ...options.headers,
      },
    };

    const response = await fetch(`${API_BASE_URL}${path}`, config);
    const body = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(body.message || body.error || "Request failed");
    }

    return body;
  }

  // Job Tags
  getJobTags() {
    return this.request("/job_tags");
  }

  updateJobTags(preferred_tags) {
    return this.request("/job_tags", {
      method: "PUT",
      body: JSON.stringify({ job_tags: { preferred_tags } }),
    });
  }

  triggerJobTagRollout() {
    return this.request("/job_tags/rollout", { method: "POST" });
  }

  // Click Optimization
  rankJobs(job_ids, context = "dashboard") {
    return this.request("/click_optimizations", {
      method: "POST",
      body: JSON.stringify({ job_ids, context }),
    });
  }

  // Career Misconduct
  fetchMisconductSummary() {
    return this.request("/career_misconducts");
  }

  submitMisconduct(report) {
    return this.request("/career_misconducts", {
      method: "POST",
      body: JSON.stringify(report),
    });
  }

  blockUser(payload) {
    return this.request("/career_misconducts/block", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  unblockUser(payload) {
    return this.request("/career_misconducts/unblock", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // Highlights
  getHighlights(job_ids) {
    const query = new URLSearchParams({ job_ids: job_ids.join(",") }).toString();
    return this.request(`/job_highlights?${query}`);
  }

  createHighlight(payload) {
    return this.request("/job_highlights", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  triggerHighlightBackfill(batch_size) {
    return this.request("/job_highlights/backfill", {
      method: "POST",
      body: JSON.stringify({ batch_size }),
    });
  }
}

export default new ApiClient();

