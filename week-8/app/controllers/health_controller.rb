class HealthController < ApplicationController
  def check
    health_status = {
      status: 'ok',
      timestamp: Time.current.iso8601,
      version: Rails.application.config.version || '1.0.0',
      environment: Rails.env,
      checks: {}
    }
    
    # Check database connectivity
    health_status[:checks][:database] = check_database_health
    
    # Check Redis connectivity
    health_status[:checks][:redis] = check_redis_health
    
    # Check Sidekiq workers
    health_status[:checks][:sidekiq] = check_sidekiq_health
    
    # Check file system (for resume storage)
    health_status[:checks][:storage] = check_storage_health
    
    # Check external services (if any)
    health_status[:checks][:external_services] = check_external_services_health
    
    # Determine overall status
    all_checks_passed = health_status[:checks].all? { |_, check| check[:status] == 'ok' }
    health_status[:status] = all_checks_passed ? 'ok' : 'degraded'
    
    # Set appropriate HTTP status
    http_status = all_checks_passed ? :ok : :service_unavailable
    
    render json: health_status, status: http_status
  end

  private

  def check_database_health
    start_time = Time.current
    
    begin
      # Test basic connectivity
      ActiveRecord::Base.connection.execute('SELECT 1')
      
      # Test a simple query
      User.count
      
      response_time = ((Time.current - start_time) * 1000).to_i
      
      {
        status: 'ok',
        response_time_ms: response_time,
        message: 'Database connection successful'
      }
    rescue => e
      {
        status: 'error',
        error: e.message,
        message: 'Database connection failed'
      }
    end
  end

  def check_redis_health
    start_time = Time.current
    
    begin
      # Test Redis ping
      response = Redis.current.ping
      
      if response == 'PONG'
        response_time = ((Time.current - start_time) * 1000).to_i
        
        {
          status: 'ok',
          response_time_ms: response_time,
          message: 'Redis connection successful'
        }
      else
        {
          status: 'error',
          error: 'Unexpected Redis response',
          message: 'Redis ping failed'
        }
      end
    rescue => e
      {
        status: 'error',
        error: e.message,
        message: 'Redis connection failed'
      }
    end
  end

  def check_sidekiq_health
    begin
      # Check if Sidekiq workers are running
      workers = Sidekiq::Workers.new
      worker_count = workers.size
      
      # Check queue sizes
      queues = Sidekiq::Queue.all
      total_queue_size = queues.sum(&:size)
      
      if worker_count > 0
        {
          status: 'ok',
          worker_count: worker_count,
          total_queue_size: total_queue_size,
          message: 'Sidekiq workers are running'
        }
      else
        {
          status: 'warning',
          worker_count: worker_count,
          total_queue_size: total_queue_size,
          message: 'No Sidekiq workers detected'
        }
      end
    rescue => e
      {
        status: 'error',
        error: e.message,
        message: 'Sidekiq health check failed'
      }
    end
  end

  def check_storage_health
    begin
      # Check if storage directory exists and is writable
      storage_path = Rails.root.join('storage')
      
      unless Dir.exist?(storage_path)
        FileUtils.mkdir_p(storage_path)
      end
      
      # Test write permissions
      test_file = storage_path.join("health_check_#{SecureRandom.hex(8)}.tmp")
      File.write(test_file, 'health check')
      File.delete(test_file)
      
      {
        status: 'ok',
        storage_path: storage_path.to_s,
        message: 'Storage is accessible and writable'
      }
    rescue => e
      {
        status: 'error',
        error: e.message,
        message: 'Storage health check failed'
      }
    end
  end

  def check_external_services_health
    # This would check external services like:
    # - Email service (if using external provider)
    # - File storage service (AWS S3, etc.)
    # - Payment processor
    # - AI services for content enhancement
    
    # For now, return a placeholder
    {
      status: 'ok',
      message: 'No external services configured'
    }
  end
end
