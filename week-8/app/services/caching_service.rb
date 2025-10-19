class CachingService
  CACHE_KEYS = {
    popular_templates: 'popular_templates',
    user_quota: 'user_quota_%d',
    template_performance: 'template_performance_%s',
    daily_metrics: 'daily_metrics_%s',
    job_success_rates: 'job_success_rates',
    system_health: 'system_health'
  }.freeze

  CACHE_DURATIONS = {
    short: 5.minutes,
    medium: 1.hour,
    long: 1.day,
    very_long: 1.week
  }.freeze

  def self.cache_popular_templates(force_refresh: false)
    cache_key = CACHE_KEYS[:popular_templates]
    
    if force_refresh || !Rails.cache.exist?(cache_key)
      templates = ResumeTemplate.popular_templates(20).map do |template|
        {
          id: template.id,
          name: template.name,
          slug: template.slug,
          category: template.category,
          is_premium: template.is_premium,
          usage_count: template.usage_count,
          generation_time_avg: template.generation_time_avg
        }
      end
      
      Rails.cache.write(cache_key, templates, expires_in: CACHE_DURATIONS[:medium])
      templates
    else
      Rails.cache.read(cache_key)
    end
  end

  def self.cache_user_quota(user_id, force_refresh: false)
    cache_key = CACHE_KEYS[:user_quota] % user_id
    
    if force_refresh || !Rails.cache.exist?(cache_key)
      user = User.find(user_id)
      quota_data = {
        is_premium: user.premium?,
        quota_remaining: user.resume_generation_quota_remaining,
        quota_reset_date: user.premium? ? nil : 1.month.from_now,
        can_generate: user.can_generate_resume?
      }
      
      Rails.cache.write(cache_key, quota_data, expires_in: CACHE_DURATIONS[:short])
      quota_data
    else
      Rails.cache.read(cache_key)
    end
  end

  def self.cache_template_performance(template_slug, force_refresh: false)
    cache_key = CACHE_KEYS[:template_performance] % template_slug
    
    if force_refresh || !Rails.cache.exist?(cache_key)
      template = ResumeTemplate.find_by(slug: template_slug)
      return nil unless template
      
      performance_data = {
        id: template.id,
        name: template.name,
        slug: template.slug,
        usage_count: template.usage_count,
        generation_time_avg: template.generation_time_avg,
        success_rate: calculate_template_success_rate(template),
        last_updated: template.updated_at
      }
      
      Rails.cache.write(cache_key, performance_data, expires_in: CACHE_DURATIONS[:medium])
      performance_data
    else
      Rails.cache.read(cache_key)
    end
  end

  def self.cache_daily_metrics(date = Date.current, force_refresh: false)
    cache_key = CACHE_KEYS[:daily_metrics] % date.strftime('%Y-%m-%d')
    
    if force_refresh || !Rails.cache.exist?(cache_key)
      metrics = calculate_daily_metrics(date)
      Rails.cache.write(cache_key, metrics, expires_in: CACHE_DURATIONS[:long])
      metrics
    else
      Rails.cache.read(cache_key)
    end
  end

  def self.cache_job_success_rates(force_refresh: false)
    cache_key = CACHE_KEYS[:job_success_rates]
    
    if force_refresh || !Rails.cache.exist?(cache_key)
      success_rates = {}
      
      JobExecution.distinct.pluck(:job_name).each do |job_name|
        success_rates[job_name] = {
          success_rate: JobExecution.success_rate_for_job(job_name, 7),
          avg_execution_time: JobExecution.average_execution_time(job_name, 7),
          total_executions: JobExecution.by_job_name(job_name)
                                      .where(created_at: 7.days.ago..Time.current)
                                      .count
        }
      end
      
      Rails.cache.write(cache_key, success_rates, expires_in: CACHE_DURATIONS[:short])
      success_rates
    else
      Rails.cache.read(cache_key)
    end
  end

  def self.cache_system_health(force_refresh: false)
    cache_key = CACHE_KEYS[:system_health]
    
    if force_refresh || !Rails.cache.exist?(cache_key)
      health_data = {
        redis_status: check_redis_health,
        database_status: check_database_health,
        sidekiq_status: check_sidekiq_health,
        last_checked: Time.current
      }
      
      Rails.cache.write(cache_key, health_data, expires_in: CACHE_DURATIONS[:short])
      health_data
    else
      Rails.cache.read(cache_key)
    end
  end

  def self.warm_up_caches
    Rails.logger.info "Warming up application caches..."
    
    # Warm up popular templates
    cache_popular_templates(force_refresh: true)
    
    # Warm up job success rates
    cache_job_success_rates(force_refresh: true)
    
    # Warm up system health
    cache_system_health(force_refresh: true)
    
    # Warm up recent daily metrics
    (0..6).each do |days_ago|
      date = days_ago.days.ago.to_date
      cache_daily_metrics(date, force_refresh: true)
    end
    
    Rails.logger.info "Cache warm-up completed"
  end

  def self.clear_user_cache(user_id)
    cache_key = CACHE_KEYS[:user_quota] % user_id
    Rails.cache.delete(cache_key)
  end

  def self.clear_template_cache(template_slug)
    cache_key = CACHE_KEYS[:template_performance] % template_slug
    Rails.cache.delete(cache_key)
  end

  def self.clear_all_caches
    Rails.logger.info "Clearing all application caches..."
    
    CACHE_KEYS.values.each do |pattern|
      if pattern.include?('%')
        # For patterns with placeholders, we can't easily clear all variants
        # In production, you might want to use Redis pattern matching
        Rails.logger.warn "Cannot clear cache pattern: #{pattern}"
      else
        Rails.cache.delete(pattern)
      end
    end
    
    Rails.logger.info "Cache clearing completed"
  end

  private

  def self.calculate_template_success_rate(template)
    resumes = Resume.where(template_name: template.name)
                   .where('created_at > ?', 30.days.ago)
    
    return 0 if resumes.empty?
    
    successful_count = resumes.where(status: 'completed').count
    total_count = resumes.count
    
    (successful_count.to_f / total_count * 100).round(2)
  end

  def self.calculate_daily_metrics(date)
    start_time = date.beginning_of_day
    end_time = date.end_of_day
    
    {
      date: date.strftime('%Y-%m-%d'),
      user_signups: User.where(created_at: start_time..end_time).count,
      resume_generations: Resume.where(created_at: start_time..end_time).count,
      completed_resumes: Resume.where(created_at: start_time..end_time, status: 'completed').count,
      premium_conversions: User.where(created_at: start_time..end_time, is_premium: true).count,
      job_executions: JobExecution.where(created_at: start_time..end_time).count,
      successful_jobs: JobExecution.where(created_at: start_time..end_time, success: true).count,
      failed_jobs: JobExecution.where(created_at: start_time..end_time, success: false).count
    }
  end

  def self.check_redis_health
    Redis.current.ping == 'PONG' ? 'healthy' : 'unhealthy'
  rescue => e
    "error: #{e.message}"
  end

  def self.check_database_health
    ActiveRecord::Base.connection.execute('SELECT 1')
    'healthy'
  rescue => e
    "error: #{e.message}"
  end

  def self.check_sidekiq_health
    worker_count = Sidekiq::Workers.new.size
    worker_count > 0 ? 'healthy' : 'no_workers'
  rescue => e
    "error: #{e.message}"
  end
end
