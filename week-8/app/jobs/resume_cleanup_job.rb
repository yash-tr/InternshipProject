class ResumeCleanupJob < ApplicationJob
  queue_as :maintenance
  retry_on StandardError, wait: :exponentially_longer, attempts: 3

  def perform
    execution = JobExecution.create!(
      job_name: 'ResumeCleanupJob',
      status: 'pending',
      parameters: {},
      queue_name: 'maintenance'
    )

    execution.mark_as_started!

    begin
      Rails.logger.info "Starting ResumeCleanupJob execution #{execution.id}"
      
      cleanup_old_files
      cleanup_failed_generations
      optimize_database_indexes
      
      execution.mark_as_completed!({
        files_cleaned: @files_cleaned,
        failed_generations_cleaned: @failed_cleaned,
        execution_time: execution.duration_seconds
      })
      
      Rails.logger.info "ResumeCleanupJob execution #{execution.id} completed successfully"
      
    rescue => e
      Rails.logger.error "ResumeCleanupJob execution #{execution.id} failed: #{e.message}"
      execution.mark_as_failed!(e.message)
      raise e
    end
  end

  private

  def cleanup_old_files
    Rails.logger.info "Cleaning up old resume files..."
    
    @files_cleaned = 0
    cutoff_date = 90.days.ago
    
    # Find resumes with files older than cutoff
    old_resumes = Resume.where('created_at < ? AND file_path IS NOT NULL', cutoff_date)
    
    old_resumes.find_each do |resume|
      if resume.file_path && File.exist?(resume.file_path)
        File.delete(resume.file_path)
        resume.update!(file_path: nil)
        @files_cleaned += 1
      end
    end
    
    Rails.logger.info "Cleaned up #{@files_cleaned} old resume files"
  end

  def cleanup_failed_generations
    Rails.logger.info "Cleaning up failed resume generations..."
    
    @failed_cleaned = 0
    cutoff_date = 7.days.ago
    
    # Clean up failed generations older than 7 days
    failed_resumes = Resume.where(
      status: 'failed',
      created_at: ...cutoff_date
    )
    
    @failed_cleaned = failed_resumes.count
    failed_resumes.delete_all
    
    Rails.logger.info "Cleaned up #{@failed_cleaned} failed resume generations"
  end

  def optimize_database_indexes
    Rails.logger.info "Optimizing database indexes..."
    
    # This would typically run ANALYZE on PostgreSQL
    # In a real application, you might want to run this less frequently
    if Rails.env.production?
      ActiveRecord::Base.connection.execute('ANALYZE resumes')
      ActiveRecord::Base.connection.execute('ANALYZE job_executions')
      ActiveRecord::Base.connection.execute('ANALYZE analytics_events')
    end
    
    Rails.logger.info "Database optimization completed"
  end
end
