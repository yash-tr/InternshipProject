// API Client extensions for Week 11 features
// Base API client functionality

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:3000/api/v1';

class ApiClient {
  constructor() {
    this.authToken = localStorage.getItem('auth_token');
  }

  getHeaders(includeAuth = true) {
    const headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    };

    if (includeAuth && this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }

    return headers;
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const config = {
      ...options,
      headers: {
        ...this.getHeaders(),
        ...options.headers
      }
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json();

      if (response.status === 401) {
        this.handleUnauthorized();
      }

      return this.handleResponse(response, data);
    } catch (error) {
      return {
        success: false,
        error: error.name,
        message: error.message
      };
    }
  }

  handleResponse(response, data) {
    if (response.ok) {
      return {
        success: true,
        data: data.data || data
      };
    }

    return {
      success: false,
      error: data.error || 'Unknown Error',
      message: data.message || 'An error occurred',
      details: data.details
    };
  }

  handleUnauthorized() {
    localStorage.removeItem('auth_token');
    window.location.href = '/login';
  }

  setAuthToken(token) {
    this.authToken = token;
    localStorage.setItem('auth_token', token);
  }
}

const apiClient = new ApiClient();

// Flagging API calls
apiClient.getFlags = async function(params = {}) {
  const queryString = new URLSearchParams(params).toString();
  return await this.request(`/flagging?${queryString}`, {
    method: 'GET'
  });
};

apiClient.createFlag = async function(flagData) {
  return await this.request('/flagging', {
    method: 'POST',
    body: JSON.stringify({ flag: flagData })
  });
};

apiClient.resolveFlag = async function(flagId, resolutionNotes) {
  return await this.request(`/flagging/${flagId}/resolve`, {
    method: 'PATCH',
    body: JSON.stringify({ resolution_notes: resolutionNotes })
  });
};

apiClient.getFlagStatistics = async function() {
  return await this.request('/flagging/statistics', {
    method: 'GET'
  });
};

// Policy API calls
apiClient.getPolicy = async function() {
  return await this.request('/policy_misconduct', {
    method: 'GET'
  });
};

apiClient.checkPolicyAcknowledgment = async function() {
  return await this.request('/policy_misconduct/check_acknowledgment', {
    method: 'GET'
  });
};

apiClient.acknowledgePolicy = async function(policyId) {
  return await this.request(`/policy_misconduct/${policyId}/acknowledge`, {
    method: 'POST'
  });
};

apiClient.reportMisconduct = async function(reportData) {
  return await this.request('/policy_misconduct/report', {
    method: 'POST',
    body: JSON.stringify({ report: reportData })
  });
};

// User Blocker API calls
apiClient.checkBlockStatus = async function(userId) {
  return await this.request(`/user_blocker/${userId}/check`, {
    method: 'GET'
  });
};

apiClient.getBlockedUsers = async function(params = {}) {
  const queryString = new URLSearchParams(params).toString();
  return await this.request(`/user_blocker?${queryString}`, {
    method: 'GET'
  });
};

apiClient.blockUser = async function(userId, blockData) {
  return await this.request(`/user_blocker/${userId}/block`, {
    method: 'POST',
    body: JSON.stringify(blockData)
  });
};

apiClient.unblockUser = async function(userId, reason) {
  return await this.request(`/user_blocker/${userId}/unblock`, {
    method: 'POST',
    body: JSON.stringify({ reason })
  });
};

// Jobs API calls
apiClient.getJobs = async function(params = {}) {
  const queryString = new URLSearchParams(params).toString();
  return await this.request(`/jobs?${queryString}`, {
    method: 'GET'
  });
};

apiClient.saveJob = async function(jobId) {
  return await this.request(`/jobs/${jobId}/save`, {
    method: 'POST'
  });
};

apiClient.unsaveJob = async function(jobId) {
  return await this.request(`/jobs/${jobId}/unsave`, {
    method: 'DELETE'
  });
};

apiClient.getSavedJobs = async function() {
  return await this.request('/jobs/saved', {
    method: 'GET'
  });
};

export default apiClient;

