// API Client for React Frontend
// Handles all API calls with proper error handling and token management

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:3000/api/v1';

class ApiClient {
  constructor() {
    this.authToken = localStorage.getItem('auth_token');
  }

  // Helper method to get headers
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

  // Helper method to make requests
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

      // Handle authentication errors
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

  // Handle API responses
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

  // Handle unauthorized access
  handleUnauthorized() {
    localStorage.removeItem('auth_token');
    window.location.href = '/login';
  }

  // Authentication API Calls
  async login(email, password) {
    return await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
  }

  async logout() {
    const result = await this.request('/auth/logout', {
      method: 'POST'
    });
    
    localStorage.removeItem('auth_token');
    return result;
  }

  async getMe() {
    return await this.request('/auth/me', {
      method: 'GET'
    });
  }

  // Resume API Calls
  async getResumes(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return await this.request(`/resumes?${queryString}`, {
      method: 'GET'
    });
  }

  async getResume(id) {
    return await this.request(`/resumes/${id}`, {
      method: 'GET'
    });
  }

  async createResume(resumeData) {
    return await this.request('/resumes', {
      method: 'POST',
      body: JSON.stringify({ resume: resumeData })
    });
  }

  async updateResume(id, resumeData) {
    return await this.request(`/resumes/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ resume: resumeData })
    });
  }

  async deleteResume(id) {
    return await this.request(`/resumes/${id}`, {
      method: 'DELETE'
    });
  }

  async generatePDF(resumeId) {
    return await this.request(`/resumes/${resumeId}/generate_pdf`, {
      method: 'POST'
    });
  }

  async optimizeResume(resumeId) {
    return await this.request(`/resumes/${resumeId}/optimize`, {
      method: 'POST'
    });
  }

  async regenerateResume(resumeId) {
    return await this.request(`/resumes/${resumeId}/regenerate`, {
      method: 'PATCH'
    });
  }

  // Template API Calls
  async getTemplates(params = {}) {
    const queryString = new URLSearchParams(params).toString();
    return await this.request(`/templates?${queryString}`, {
      method: 'GET'
    });
  }

  async getPopularTemplates() {
    return await this.request('/templates/popular', {
      method: 'GET'
    });
  }

  async getFastestTemplates() {
    return await this.request('/templates/fastest', {
      method: 'GET'
    });
  }

  async getTemplatesByCategory(category) {
    return await this.request(`/templates/by_category?category=${category}`, {
      method: 'GET'
    });
  }

  // Analytics API Calls
  async getDashboardAnalytics() {
    return await this.request('/analytics/dashboard', {
      method: 'GET'
    });
  }

  async getUserMetrics() {
    return await this.request('/analytics/user_metrics', {
      method: 'GET'
    });
  }

  async getResumeAnalytics() {
    return await this.request('/resumes/analytics', {
      method: 'GET'
    });
  }

  async getSystemHealth() {
    return await this.request('/analytics/system_health', {
      method: 'GET'
    });
  }

  // User API Calls
  async getUserProfile(userId) {
    return await this.request(`/users/${userId}`, {
      method: 'GET'
    });
  }

  async updateUserProfile(userId, userData) {
    return await this.request(`/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ user: userData })
    });
  }

  async getUserQuota(userId) {
    return await this.request(`/users/${userId}/quota`, {
      method: 'GET'
    });
  }

  async upgradeSubscription(userId, tier) {
    return await this.request(`/users/${userId}/upgrade_subscription`, {
      method: 'PATCH',
      body: JSON.stringify({ tier })
    });
  }

  // Set auth token after login
  setAuthToken(token) {
    this.authToken = token;
    localStorage.setItem('auth_token', token);
  }
}

// Export singleton instance
export default new ApiClient();

