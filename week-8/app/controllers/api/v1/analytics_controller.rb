class Api::V1::AnalyticsController < ApplicationController
  before_action :authenticate_user!

  def dashboard
    # Get cached analytics data for better performance
    daily_metrics = CachingService.cache_daily_metrics(Date.current)
    job_success_rates = CachingService.cache_job_success_rates
    system_health = CachingService.cache_system_health
    
    dashboard_data = {
      daily_metrics: daily_metrics,
      job_success_rates: job_success_rates,
      system_health: system_health,
      user_metrics: user_metrics,
      resume_metrics: resume_metrics
    }
    
    render json: {
      success: true,
      dashboard: dashboard_data
    }
  end

  def user_metrics
    metrics = {
      total_users: User.count,
      premium_users: User.premium.count,
      active_users: User.where('last_sign_in_at > ?', 7.days.ago).count,
      new_users_today: User.where(created_at: Date.current.beginning_of_day..Date.current.end_of_day).count,
      conversion_rate: calculate_conversion_rate,
      retention_rate: calculate_retention_rate
    }
    
    render json: {
      success: true,
      user_metrics: metrics
    }
  end

  def system_health
    health_data = CachingService.cache_system_health(force_refresh: true)
    
    # Add additional health checks
    health_data[:sidekiq_queues] = check_sidekiq_queues
    health_data[:database_size] = check_database_size
    health_data[:cache_hit_rate] = check_cache_hit_rate
    
    render json: {
      success: true,
      system_health: health_data
    }
  end

  def job_metrics
    job_metrics = CachingService.cache_job_success_rates(force_refresh: true)
    
    # Add recent job executions
    recent_executions = JobExecution.recent.limit(50).map do |execution|
      {
        id: execution.id,
        job_name: execution.job_name,
        status: execution.status,
        success: execution.success,
        started_at: execution.started_at,
        completed_at: execution.completed_at,
        execution_time_ms: execution.execution_time_ms,
        error_message: execution.error_message
      }
    end
    
    render json: {
      success: true,
      job_metrics: job_metrics,
      recent_executions: recent_executions
    }
  end

  def conversion_funnel
    funnel_data = {
      page_views: AnalyticsEvent.where(event_name: 'page_view')
                               .where(occurred_at: 7.days.ago..Time.current)
                               .count,
      resume_started: AnalyticsEvent.where(event_name: 'resume_started')
                                   .where(occurred_at: 7.days.ago..Time.current)
                                   .count,
      resume_completed: AnalyticsEvent.where(event_name: 'resume_completed')
                                     .where(occurred_at: 7.days.ago..Time.current)
                                     .count,
      resume_downloaded: AnalyticsEvent.where(event_name: 'resume_downloaded')
                                      .where(occurred_at: 7.days.ago..Time.current)
                                      .count,
      premium_conversions: User.where(is_premium: true)
                              .where(created_at: 7.days.ago..Time.current)
                              .count
    }
    
    # Calculate conversion rates
    funnel_data[:conversion_rates] = {
      view_to_start: calculate_conversion_rate(funnel_data[:page_views], funnel_data[:resume_started]),
      start_to_complete: calculate_conversion_rate(funnel_data[:resume_started], funnel_data[:resume_completed]),
      complete_to_download: calculate_conversion_rate(funnel_data[:resume_completed], funnel_data[:resume_downloaded]),
      overall_conversion: calculate_conversion_rate(funnel_data[:page_views], funnel_data[:resume_downloaded])
    }
    
    render json: {
      success: true,
      conversion_funnel: funnel_data
    }
  end

  private

  def user_metrics
    {
      total_resumes: current_user.resumes.count,
      completed_resumes: current_user.resumes.completed.count,
      quota_remaining: current_user.resume_generation_quota_remaining,
      is_premium: current_user.premium?,
      last_activity: current_user.resumes.maximum(:updated_at)
    }
  end

  def resume_metrics
    {
      total_generations: Resume.count,
      completed_generations: Resume.completed.count,
      failed_generations: Resume.where(status: 'failed').count,
      avg_generation_time: Resume.completed.average(:generation_time_ms),
      premium_generations: Resume.joins(:user).where(users: { is_premium: true }).count,
      free_generations: Resume.joins(:user).where(users: { is_premium: false }).count
    }
  end

  def calculate_conversion_rate(numerator, denominator)
    return 0 if denominator.zero?
    (numerator.to_f / denominator * 100).round(2)
  end

  def check_sidekiq_queues
    queues = {}
    
    Sidekiq::Queue.all.each do |queue|
      queues[queue.name] = {
        size: queue.size,
        latency: queue.latency
      }
    end
    
    queues
  rescue => e
    { error: e.message }
  end

  def check_database_size
    # This would be database-specific
    # For PostgreSQL:
    result = ActiveRecord::Base.connection.execute(
      "SELECT pg_size_pretty(pg_database_size(current_database())) as size"
    )
    result.first['size']
  rescue => e
    "Error: #{e.message}"
  end

  def check_cache_hit_rate
    # This would require Redis monitoring
    # For now, return a placeholder
    "N/A"
  end
end
