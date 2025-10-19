class AutomationJob < ApplicationJob
  queue_as :automation
  retry_on StandardError, wait: :exponentially_longer, attempts: 3

  def perform(*args)
    execution = JobExecution.create!(
      job_name: 'AutomationJob',
      status: 'pending',
      parameters: args,
      queue_name: 'automation'
    )

    execution.mark_as_started!

    begin
      Rails.logger.info "Starting AutomationJob execution #{execution.id}"
      
      # Main automation tasks
      perform_data_cleanup
      perform_analytics_aggregation
      perform_system_health_check
      perform_cache_optimization
      
      execution.mark_as_completed!({
        tasks_completed: 4,
        execution_time: execution.duration_seconds
      })
      
      Rails.logger.info "AutomationJob execution #{execution.id} completed successfully"
      
    rescue => e
      Rails.logger.error "AutomationJob execution #{execution.id} failed: #{e.message}"
      execution.mark_as_failed!(e.message)
      
      # Send alert for critical automation failures
      AlertingService.new.send_automation_failure_alert(execution, e)
      
      raise e
    end
  end

  private

  def perform_data_cleanup
    Rails.logger.info "Performing data cleanup..."
    
    # Clean up old job executions (keep last 30 days)
    old_executions = JobExecution.where('created_at < ?', 30.days.ago)
    deleted_count = old_executions.count
    old_executions.delete_all
    
    Rails.logger.info "Cleaned up #{deleted_count} old job executions"
  end

  def perform_analytics_aggregation
    Rails.logger.info "Performing analytics aggregation..."
    
    # Aggregate daily analytics
    AnalyticsAggregationJob.perform_later
    
    Rails.logger.info "Analytics aggregation job queued"
  end

  def perform_system_health_check
    Rails.logger.info "Performing system health check..."
    
    # Check Redis connection
    Redis.current.ping
    
    # Check database connection
    ActiveRecord::Base.connection.execute('SELECT 1')
    
    # Check Sidekiq workers
    worker_count = Sidekiq::Workers.new.size
    Rails.logger.info "Active Sidekiq workers: #{worker_count}"
    
    if worker_count == 0
      raise "No active Sidekiq workers detected"
    end
  end

  def perform_cache_optimization
    Rails.logger.info "Performing cache optimization..."
    
    # Clear expired cache entries
    Rails.cache.cleanup
    
    # Warm up frequently accessed caches
    ResumeTemplate.popular_templates.each do |template|
      Rails.cache.write("template_#{template.id}", template, expires_in: 1.hour)
    end
    
    Rails.logger.info "Cache optimization completed"
  end
end
