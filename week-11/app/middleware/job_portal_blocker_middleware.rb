# Job Portal Blocker Middleware
# Blocks access to job portal for users with active blocks

class JobPortalBlockerMiddleware
  def initialize(app)
    @app = app
  end

  def call(env)
    request = ActionDispatch::Request.new(env)

    # Only apply to job portal routes
    return @app.call(env) unless job_portal_route?(request)

    # Check if user is authenticated
    user = env['current_user']
    return @app.call(env) unless user

    # Check if user is blocked
    blocker = UserBlockerService.new(user)
    block_status = blocker.check_block_status

    if block_status[:is_blocked] && !blocker.can_access_job_portal?
      return blocked_response(block_status[:block])
    end

    @app.call(env)
  rescue => e
    Rails.logger.error "Job Portal Blocker Middleware Error: #{e.message}"
    # On error, allow access (fail open)
    @app.call(env)
  end

  private

  def job_portal_route?(request)
    request.path.start_with?('/jobs') || 
    request.path.start_with?('/api/v1/jobs')
  end

  def blocked_response(block)
    [403, 
     { 'Content-Type' => 'application/json' },
     [{
       success: false,
       error: 'Access Restricted',
       message: 'Your access to the job portal has been restricted',
       reason: block.reason,
       expires_at: block.expires_at,
       block_type: block.block_type
     }.to_json]]
  end
end

