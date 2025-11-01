# Rate Limiting Middleware
# Prevents API abuse with configurable rate limits per user/IP

class RateLimitingMiddleware
  def initialize(app)
    @app = app
    @redis = Redis.new(url: ENV.fetch('REDIS_URL', 'redis://localhost:6379/0'))
    @default_limit = 100 # requests per window
    @window_size = 60 # seconds
  end

  def call(env)
    request = ActionDispatch::Request.new(env)
    user_id = env['current_user']&.id
    
    # Skip rate limiting for certain endpoints
    return @app.call(env) if exempt_endpoint?(request)

    # Check rate limit
    if rate_limit_exceeded?(request, user_id)
      return rate_limit_exceeded_response
    end

    # Increment counter and proceed
    increment_counter(request, user_id)
    @app.call(env)
  rescue => e
    Rails.logger.error "Rate limiting error: #{e.message}"
    # On error, allow request through
    @app.call(env)
  end

  private

  def exempt_endpoint?(request)
    exempt_paths = ['/health', '/api/v1/health']
    exempt_paths.any? { |path| request.path == path }
  end

  def rate_limit_exceeded?(request, user_id)
    key = rate_limit_key(request, user_id)
    current = @redis.get(key).to_i
    
    current >= rate_limit_for(user_id)
  end

  def increment_counter(request, user_id)
    key = rate_limit_key(request, user_id)
    
    # Increment and set expiry
    @redis.incr(key)
    @redis.expire(key, @window_size)
  end

  def rate_limit_key(request, user_id)
    # Use user_id if authenticated, otherwise use IP
    identifier = user_id || request.remote_ip
    "rate_limit:#{identifier}:#{window_timestamp}"
  end

  def window_timestamp
    (Time.now.to_i / @window_size)
  end

  def rate_limit_for(user_id)
    # Premium users get higher limits
    return @default_limit * 2 if user_id && User.find_by(id: user_id)&.premium?
    
    @default_limit
  end

  def rate_limit_exceeded_response
    [429, 
     { 'Content-Type' => 'application/json',
       'Retry-After' => @window_size.to_s },
     [{
       success: false,
       error: 'Rate Limit Exceeded',
       message: 'Too many requests. Please try again later.',
       retry_after: @window_size
     }.to_json]]
  end
end

