require 'sidekiq'
require 'sidekiq-cron'
require 'sidekiq-scheduler'

Sidekiq.configure_server do |config|
  config.redis = { url: ENV.fetch('REDIS_URL', 'redis://localhost:6379/0') }
  
  # Configure job retry
  config.retry_jobs = true
  config.retry_in = 5 * 60 # 5 minutes
  
  # Configure job timeout
  config.timeout = 30
  
  # Configure concurrency
  config.concurrency = ENV.fetch('SIDEKIQ_CONCURRENCY', 10).to_i
end

Sidekiq.configure_client do |config|
  config.redis = { url: ENV.fetch('REDIS_URL', 'redis://localhost:6379/0') }
end

# Load scheduled jobs
Sidekiq::Cron::Job.load_from_hash!({
  'automation_job' => {
    'class' => 'AutomationJob',
    'cron' => '0 */6 * * *', # Every 6 hours
    'args' => []
  },
  'resume_cleanup_job' => {
    'class' => 'ResumeCleanupJob',
    'cron' => '0 2 * * *', # Daily at 2 AM
    'args' => []
  },
  'analytics_aggregation_job' => {
    'class' => 'AnalyticsAggregationJob',
    'cron' => '0 1 * * *', # Daily at 1 AM
    'args' => []
  }
})
