# Redis configuration
redis_config = {
  url: ENV.fetch('REDIS_URL', 'redis://localhost:6379/0'),
  timeout: 5,
  connect_timeout: 5,
  read_timeout: 5,
  write_timeout: 5,
  reconnect_attempts: 3,
  reconnect_delay: 0.5,
  reconnect_delay_max: 2.0
}

# Configure Redis for different environments
if Rails.env.production?
  redis_config.merge!(
    ssl: true,
    ssl_params: { verify_mode: OpenSSL::SSL::VERIFY_NONE }
  )
end

# Set up Redis connection
Redis.current = Redis.new(redis_config)

# Configure Redis for Sidekiq
Sidekiq.configure_server do |config|
  config.redis = redis_config
end

Sidekiq.configure_client do |config|
  config.redis = redis_config
end

# Configure Redis for Rails cache
Rails.application.configure do
  config.cache_store = :redis_cache_store, {
    url: redis_config[:url],
    namespace: 'resume_builder',
    expires_in: 1.hour,
    race_condition_ttl: 10.seconds
  }
end
