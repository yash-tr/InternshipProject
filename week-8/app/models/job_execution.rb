class JobExecution < ApplicationRecord
  validates :job_name, presence: true
  validates :status, inclusion: { in: %w[pending running completed failed retrying] }

  scope :recent, -> { order(created_at: :desc) }
  scope :successful, -> { where(success: true) }
  scope :failed, -> { where(success: false) }
  scope :by_job_name, ->(name) { where(job_name: name) }

  def duration_seconds
    return nil unless started_at && completed_at
    (completed_at - started_at).to_f
  end

  def duration_ms
    return nil unless duration_seconds
    (duration_seconds * 1000).to_i
  end

  def mark_as_started!(worker_id = nil)
    update!(
      status: 'running',
      started_at: Time.current,
      worker_id: worker_id
    )
  end

  def mark_as_completed!(result = {})
    update!(
      status: 'completed',
      completed_at: Time.current,
      success: true,
      result: result,
      execution_time_ms: duration_ms
    )
  end

  def mark_as_failed!(error_message)
    update!(
      status: 'failed',
      completed_at: Time.current,
      success: false,
      error_message: error_message,
      execution_time_ms: duration_ms
    )
  end

  def retry!
    update!(
      status: 'retrying',
      retry_count: retry_count + 1,
      started_at: nil,
      completed_at: nil,
      error_message: nil
    )
  end

  def self.success_rate_for_job(job_name, days = 7)
    executions = by_job_name(job_name)
                  .where(created_at: days.days.ago..Time.current)
                  .where.not(status: 'pending')
    
    return 0 if executions.empty?
    
    successful_count = executions.successful.count
    total_count = executions.count
    
    (successful_count.to_f / total_count * 100).round(2)
  end

  def self.average_execution_time(job_name, days = 7)
    executions = by_job_name(job_name)
                  .where(created_at: days.days.ago..Time.current)
                  .where.not(execution_time_ms: nil)
    
    return 0 if executions.empty?
    
    executions.average(:execution_time_ms).to_f.round(2)
  end
end
