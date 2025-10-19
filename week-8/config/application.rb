require_relative "boot"

require "rails/all"

Bundler.require(*Rails.groups)

module ResumeBuilderPlatform
  class Application < Rails::Application
    config.load_defaults 7.0

    # Configuration for the application, engines, and railties goes here.
    config.api_only = false

    # CORS configuration
    config.middleware.insert_before 0, Rack::Cors do
      allow do
        origins '*'
        resource '*', headers: :any, methods: [:get, :post, :put, :patch, :delete, :options, :head]
      end
    end

    # Sidekiq configuration
    config.active_job.queue_adapter = :sidekiq

    # Redis configuration
    config.cache_store = :redis_cache_store, { url: ENV.fetch('REDIS_URL', 'redis://localhost:6379/0') }

    # Logging configuration
    config.lograge.enabled = true
    config.lograge.formatter = Lograge::Formatters::Json.new

    # Time zone
    config.time_zone = 'UTC'

    # Autoload paths
    config.autoload_paths += %W(#{config.root}/app/services)
    config.autoload_paths += %W(#{config.root}/app/workers)
    config.autoload_paths += %W(#{config.root}/app/jobs)
  end
end
