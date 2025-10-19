class ApplicationController < ActionController::API
  include ActionController::Cookies
  include ActionController::RequestForgeryProtection
  
  # Enable CSRF protection
  protect_from_forgery with: :exception
  
  # Handle exceptions
  rescue_from StandardError, with: :handle_standard_error
  rescue_from ActiveRecord::RecordNotFound, with: :handle_not_found
  rescue_from ActiveRecord::RecordInvalid, with: :handle_validation_error
  rescue_from ResumeGenerationError, with: :handle_resume_generation_error
  
  # Authentication
  before_action :authenticate_user!, except: [:health_check]
  
  # CORS headers
  after_action :set_cors_headers
  
  # Request logging
  before_action :log_request
  after_action :log_response

  private

  def authenticate_user!
    return if user_signed_in?
    
    render json: {
      success: false,
      error: 'Authentication required',
      code: 'AUTHENTICATION_REQUIRED'
    }, status: :unauthorized
  end

  def current_user
    @current_user ||= User.find(session[:user_id]) if session[:user_id]
  rescue ActiveRecord::RecordNotFound
    session[:user_id] = nil
    nil
  end

  def user_signed_in?
    current_user.present?
  end

  def sign_in(user)
    session[:user_id] = user.id
    @current_user = user
  end

  def sign_out(user)
    session[:user_id] = nil
    @current_user = nil
  end

  def set_cors_headers
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Content-Type, Accept, Authorization, X-Requested-With'
    response.headers['Access-Control-Max-Age'] = '1728000'
  end

  def log_request
    @request_start_time = Time.current
    
    Rails.logger.info "Request: #{request.method} #{request.path} - User: #{current_user&.id || 'Anonymous'} - IP: #{request.remote_ip}"
  end

  def log_response
    return unless @request_start_time
    
    duration = ((Time.current - @request_start_time) * 1000).to_i
    Rails.logger.info "Response: #{response.status} - Duration: #{duration}ms"
  end

  def handle_standard_error(exception)
    Rails.logger.error "Standard Error: #{exception.class.name} - #{exception.message}"
    Rails.logger.error exception.backtrace.join("\n")
    
    # Send to Sentry in production
    Sentry.capture_exception(exception) if Rails.env.production?
    
    render json: {
      success: false,
      error: Rails.env.production? ? 'Internal server error' : exception.message,
      code: 'INTERNAL_SERVER_ERROR'
    }, status: :internal_server_error
  end

  def handle_not_found(exception)
    Rails.logger.warn "Record Not Found: #{exception.message}"
    
    render json: {
      success: false,
      error: 'Resource not found',
      code: 'NOT_FOUND'
    }, status: :not_found
  end

  def handle_validation_error(exception)
    Rails.logger.warn "Validation Error: #{exception.message}"
    
    render json: {
      success: false,
      error: 'Validation failed',
      errors: exception.record.errors.full_messages,
      code: 'VALIDATION_ERROR'
    }, status: :unprocessable_entity
  end

  def handle_resume_generation_error(exception)
    Rails.logger.error "Resume Generation Error: #{exception.message}"
    
    render json: {
      success: false,
      error: exception.message,
      code: 'RESUME_GENERATION_ERROR'
    }, status: :unprocessable_entity
  end

  def render_success(data = {}, message = 'Success')
    render json: {
      success: true,
      message: message,
      data: data
    }
  end

  def render_error(error, code = 'ERROR', status = :unprocessable_entity)
    render json: {
      success: false,
      error: error,
      code: code
    }, status: status
  end
end
