class AnalyticsAggregationJob < ApplicationJob
  queue_as :analytics
  retry_on StandardError, wait: :exponentially_longer, attempts: 3

  def perform
    execution = JobExecution.create!(
      job_name: 'AnalyticsAggregationJob',
      status: 'pending',
      parameters: {},
      queue_name: 'analytics'
    )

    execution.mark_as_started!

    begin
      Rails.logger.info "Starting AnalyticsAggregationJob execution #{execution.id}"
      
      aggregate_daily_metrics
      calculate_user_retention
      analyze_resume_generation_metrics
      update_template_performance
      
      execution.mark_as_completed!({
        metrics_aggregated: @metrics_count,
        execution_time: execution.duration_seconds
      })
      
      Rails.logger.info "AnalyticsAggregationJob execution #{execution.id} completed successfully"
      
    rescue => e
      Rails.logger.error "AnalyticsAggregationJob execution #{execution.id} failed: #{e.message}"
      execution.mark_as_failed!(e.message)
      raise e
    end
  end

  private

  def aggregate_daily_metrics
    Rails.logger.info "Aggregating daily metrics..."
    
    @metrics_count = 0
    yesterday = 1.day.ago.beginning_of_day..1.day.ago.end_of_day
    
    # User signups
    signups = User.where(created_at: yesterday).count
    Rails.cache.write("daily_signups_#{Date.yesterday}", signups, expires_in: 30.days)
    @metrics_count += 1
    
    # Resume generations
    resume_generations = Resume.where(created_at: yesterday).count
    Rails.cache.write("daily_resume_generations_#{Date.yesterday}", resume_generations, expires_in: 30.days)
    @metrics_count += 1
    
    # Premium conversions
    premium_conversions = User.where(created_at: yesterday, is_premium: true).count
    Rails.cache.write("daily_premium_conversions_#{Date.yesterday}", premium_conversions, expires_in: 30.days)
    @metrics_count += 1
    
    # Job execution success rates
    JobExecution.distinct.pluck(:job_name).each do |job_name|
      success_rate = JobExecution.success_rate_for_job(job_name, 1)
      Rails.cache.write("daily_job_success_rate_#{job_name}_#{Date.yesterday}", success_rate, expires_in: 30.days)
      @metrics_count += 1
    end
    
    Rails.logger.info "Aggregated #{@metrics_count} daily metrics"
  end

  def calculate_user_retention
    Rails.logger.info "Calculating user retention..."
    
    # Calculate 7-day retention
    week_ago = 7.days.ago
    users_week_ago = User.where(created_at: week_ago.beginning_of_day..week_ago.end_of_day)
    
    retained_users = users_week_ago.joins(:analytics_events)
                                  .where(analytics_events: { 
                                    event_name: 'user_login',
                                    occurred_at: 6.days.ago..Time.current 
                                  })
                                  .distinct
                                  .count
    
    retention_rate = users_week_ago.count > 0 ? (retained_users.to_f / users_week_ago.count * 100).round(2) : 0
    Rails.cache.write("weekly_retention_rate_#{Date.current}", retention_rate, expires_in: 7.days)
    
    Rails.logger.info "7-day retention rate: #{retention_rate}%"
  end

  def analyze_resume_generation_metrics
    Rails.logger.info "Analyzing resume generation metrics..."
    
    # Average generation time by template
    ResumeTemplate.find_each do |template|
      avg_time = Resume.joins(:user)
                      .where(template_name: template.name, status: 'completed')
                      .where('generated_at > ?', 7.days.ago)
                      .average(:generation_time_ms)
      
      if avg_time
        template.update_generation_time!(avg_time.to_i)
      end
    end
    
    # Premium vs free user generation times
    premium_avg = Resume.joins(:user)
                       .where(users: { is_premium: true }, status: 'completed')
                       .where('generated_at > ?', 7.days.ago)
                       .average(:generation_time_ms)
    
    free_avg = Resume.joins(:user)
                    .where(users: { is_premium: false }, status: 'completed')
                    .where('generated_at > ?', 7.days.ago)
                    .average(:generation_time_ms)
    
    Rails.cache.write("premium_avg_generation_time", premium_avg&.to_i, expires_in: 1.day)
    Rails.cache.write("free_avg_generation_time", free_avg&.to_i, expires_in: 1.day)
    
    Rails.logger.info "Resume generation metrics analyzed"
  end

  def update_template_performance
    Rails.logger.info "Updating template performance metrics..."
    
    ResumeTemplate.find_each do |template|
      # Update usage count
      usage_count = Resume.where(template_name: template.name)
                         .where('created_at > ?', 30.days.ago)
                         .count
      
      template.update!(usage_count: usage_count) if usage_count != template.usage_count
    end
    
    Rails.logger.info "Template performance metrics updated"
  end
end
