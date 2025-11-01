# API Authentication Middleware
# Handles JWT token validation and user authentication for API requests

class ApiAuthMiddleware
  def initialize(app)
    @app = app
  end

  def call(env)
    request = ActionDispatch::Request.new(env)
    
    # Skip authentication for public endpoints
    return @app.call(env) if public_endpoint?(request)

    # Extract token from Authorization header
    token = extract_token(request)

    if token && valid_token?(token)
      # Add user to request environment
      env['current_user'] = current_user_from_token(token)
      @app.call(env)
    else
      unauthorized_response
    end
  rescue => e
    Rails.logger.error "Auth Middleware Error: #{e.message}"
    unauthorized_response
  end

  private

  def public_endpoint?(request)
    public_paths = [
      '/api/v1/auth/login',
      '/api/v1/auth/register',
      '/health',
      '/api/v1/templates'
    ]

    public_paths.any? { |path| request.path.start_with?(path) }
  end

  def extract_token(request)
    auth_header = request.headers['Authorization']
    
    return nil unless auth_header
    
    # Extract Bearer token
    match = auth_header.match(/^Bearer\s+(.+)$/)
    match ? match[1] : nil
  end

  def valid_token?(token)
    return false if token.blank?
    
    # TODO: Implement JWT validation
    # For now, validate against stored tokens
    decode_jwt_token(token).present?
  rescue => e
    Rails.logger.error "Token validation error: #{e.message}"
    false
  end

  def decode_jwt_token(token)
    # TODO: Implement JWT decoding with secret
    # This is a placeholder implementation
    JWT.decode(token, Rails.application.credentials.secret_key_base)
  rescue JWT::DecodeError => e
    Rails.logger.error "JWT decode error: #{e.message}"
    nil
  end

  def current_user_from_token(token)
    # TODO: Extract user_id from decoded token
    decoded = decode_jwt_token(token)
    return nil unless decoded
    
    user_id = decoded[0]['user_id']
    User.find_by(id: user_id)
  rescue => e
    Rails.logger.error "User lookup error: #{e.message}"
    nil
  end

  def unauthorized_response
    [401, { 'Content-Type' => 'application/json' }, [{
      success: false,
      error: 'Unauthorized',
      message: 'Invalid or expired authentication token'
    }.to_json]]
  end
end

