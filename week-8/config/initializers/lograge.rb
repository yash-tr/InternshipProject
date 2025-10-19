Rails.application.configure do
  # Lograge configuration for structured logging
  config.lograge.enabled = true
  
  # Use JSON format for better parsing
  config.lograge.formatter = Lograge::Formatters::Json.new
  
  # Customize log format
  config.lograge.custom_options = lambda do |event|
    {
      time: Time.current.iso8601,
      request_id: event.payload[:request_id],
      user_id: event.payload[:user_id],
      ip: event.payload[:ip],
      user_agent: event.payload[:user_agent],
      params: event.payload[:params].except('controller', 'action'),
      exception: event.payload[:exception]&.first,
      exception_message: event.payload[:exception]&.last
    }
  end
  
  # Add custom fields to log payload
  config.lograge.custom_payload do |controller|
    {
      user_id: controller.current_user&.id,
      ip: controller.request.remote_ip,
      user_agent: controller.request.user_agent
    }
  end
  
  # Ignore certain parameters
  config.lograge.ignore_actions = ['health#check']
  
  # Customize log level
  config.lograge.log_level = :info
end
