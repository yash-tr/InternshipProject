Sentry.init do |config|
  config.dsn = ENV.fetch('SENTRY_DSN', nil)
  config.breadcrumbs_logger = [:active_support_logger, :http_logger]
  
  # Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring
  config.traces_sample_rate = ENV.fetch('SENTRY_TRACES_SAMPLE_RATE', 0.1).to_f
  
  # Set profiles_sample_rate to profile 100% of transactions for performance monitoring
  config.profiles_sample_rate = ENV.fetch('SENTRY_PROFILES_SAMPLE_RATE', 0.1).to_f
  
  # Filter sensitive data
  config.before_send = lambda do |event, hint|
    # Filter out sensitive parameters
    if event.request&.data
      event.request.data = filter_sensitive_data(event.request.data)
    end
    event
  end
end

def filter_sensitive_data(data)
  return data unless data.is_a?(Hash)
  
  sensitive_keys = %w[password password_confirmation token secret api_key]
  
  data.transform_values do |value|
    if value.is_a?(Hash)
      filter_sensitive_data(value)
    elsif value.is_a?(String) && sensitive_keys.any? { |key| data.key?(key) }
      '[FILTERED]'
    else
      value
    end
  end
end
