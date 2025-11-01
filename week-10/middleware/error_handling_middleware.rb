# Error Handling Middleware
# Captures and formats errors for consistent API responses

class ErrorHandlingMiddleware
  def initialize(app)
    @app = app
  end

  def call(env)
    @app.call(env)
  rescue StandardError => e
    handle_error(e, env)
  end

  private

  def handle_error(error, env)
    request = ActionDispatch::Request.new(env)
    
    # Log error
    Rails.logger.error "Error: #{error.class} - #{error.message}"
    Rails.logger.error error.backtrace.join("\n")

    # Send to error tracking service
    send_to_error_tracking(error, request)

    # Format error response
    [status_code_for(error), 
     { 'Content-Type' => 'application/json' },
     [error_response(error, request).to_json]]
  end

  def status_code_for(error)
    case error
    when ActiveRecord::RecordNotFound
      404
    when ActionController::ParameterMissing,
         ActiveRecord::RecordInvalid,
         ArgumentError
      422
    when Pundit::NotAuthorizedError
      403
    else
      500
    end
  end

  def error_response(error, request)
    {
      success: false,
      error: error.class.name,
      message: user_friendly_message(error),
      request_id: request.uuid,
      timestamp: Time.current.iso8601
    }.tap do |response|
      # Add details in development
      if Rails.env.development?
        response[:details] = {
          message: error.message,
          backtrace: error.backtrace[0..5]
        }
      end
    end
  end

  def user_friendly_message(error)
    case error
    when ActiveRecord::RecordNotFound
      'The requested resource was not found'
    when ActionController::ParameterMissing
      'Required parameters are missing'
    when ActiveRecord::RecordInvalid
      error.record.errors.full_messages.join(', ')
    when Pundit::NotAuthorizedError
      'You do not have permission to perform this action'
    else
      Rails.env.development? ? error.message : 'An unexpected error occurred'
    end
  end

  def send_to_error_tracking(error, request)
    # Send to Sentry if configured
    return unless defined?(Sentry)

    Sentry.capture_exception(
      error,
      tags: {
        controller: request.controller_class&.name,
        action: request.params['action'],
        user_id: request.env['current_user']&.id
      },
      extra: {
        params: sanitized_params(request.params),
        headers: sanitized_headers(request.headers)
      }
    )
  rescue => e
    Rails.logger.error "Failed to send error to tracking: #{e.message}"
  end

  def sanitized_params(params)
    # Remove sensitive data
    params.except('password', 'password_confirmation', 'token', 'secret')
  end

  def sanitized_headers(headers)
    # Only include relevant headers
    {
      'Content-Type' => headers['Content-Type'],
      'Accept' => headers['Accept'],
      'User-Agent' => headers['User-Agent']
    }
  end
end

