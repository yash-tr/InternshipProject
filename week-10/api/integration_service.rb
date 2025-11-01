# API Integration Service
# Handles frontend-backend communication with proper error handling and token management

class ApiIntegrationService
  include HTTParty
  base_uri ENV.fetch('API_BASE_URL', 'http://localhost:3000/api/v1')

  attr_reader :auth_token, :user_id

  def initialize(auth_token = nil, user_id = nil)
    @auth_token = auth_token
    @user_id = user_id
  end

  # Authentication Methods
  def login(email, password)
    response = self.class.post('/auth/login', {
      body: { email: email, password: password },
      headers: default_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def logout
    response = self.class.post('/auth/logout', {
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def me
    response = self.class.get('/auth/me', {
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  # Resume Methods
  def get_resumes(params = {})
    response = self.class.get('/resumes', {
      query: params,
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def get_resume(id)
    response = self.class.get("/resumes/#{id}", {
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def create_resume(resume_data)
    response = self.class.post('/resumes', {
      body: { resume: resume_data },
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def update_resume(id, resume_data)
    response = self.class.patch("/resumes/#{id}", {
      body: { resume: resume_data },
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def delete_resume(id)
    response = self.class.delete("/resumes/#{id}", {
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def generate_pdf(resume_id)
    response = self.class.post("/resumes/#{resume_id}/generate_pdf", {
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def download_resume(resume_id)
    response = self.class.get("/resumes/#{resume_id}/download", {
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  # Template Methods
  def get_templates(params = {})
    response = self.class.get('/templates', {
      query: params,
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def get_popular_templates
    response = self.class.get('/templates/popular', {
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  # Analytics Methods
  def get_dashboard_analytics
    response = self.class.get('/analytics/dashboard', {
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def get_user_metrics
    response = self.class.get('/analytics/user_metrics', {
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def get_resume_analytics
    response = self.class.get('/resumes/analytics', {
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  # User Methods
  def get_user_profile
    response = self.class.get("/users/#{@user_id}", {
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def update_user_profile(user_data)
    response = self.class.patch("/users/#{@user_id}", {
      body: { user: user_data },
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def get_quota
    response = self.class.get("/users/#{@user_id}/quota", {
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  def upgrade_subscription(tier)
    response = self.class.patch("/users/#{@user_id}/upgrade_subscription", {
      body: { tier: tier },
      headers: authenticated_headers
    })

    handle_response(response)
  rescue => e
    handle_error(e)
  end

  private

  def default_headers
    {
      'Content-Type' => 'application/json',
      'Accept' => 'application/json'
    }
  end

  def authenticated_headers
    default_headers.merge({
      'Authorization' => "Bearer #{@auth_token}"
    })
  end

  def handle_response(response)
    case response.code
    when 200..299
      {
        success: true,
        data: JSON.parse(response.body)
      }
    when 400
      {
        success: false,
        error: 'Bad Request',
        details: JSON.parse(response.body)
      }
    when 401
      {
        success: false,
        error: 'Unauthorized',
        message: 'Please login again'
      }
    when 403
      {
        success: false,
        error: 'Forbidden',
        message: 'You do not have permission to perform this action'
      }
    when 404
      {
        success: false,
        error: 'Not Found',
        message: 'Resource not found'
      }
    when 422
      {
        success: false,
        error: 'Validation Error',
        details: JSON.parse(response.body)
      }
    when 500..599
      {
        success: false,
        error: 'Server Error',
        message: 'Something went wrong on the server'
      }
    else
      {
        success: false,
        error: 'Unknown Error',
        message: 'An unexpected error occurred'
      }
    end
  rescue JSON::ParserError
    {
      success: false,
      error: 'Parse Error',
      message: 'Invalid response from server'
    }
  end

  def handle_error(exception)
    Rails.logger.error "API Integration Error: #{exception.class} - #{exception.message}"
    Rails.logger.error exception.backtrace.join("\n")

    {
      success: false,
      error: exception.class.name,
      message: exception.message
    }
  end
end

