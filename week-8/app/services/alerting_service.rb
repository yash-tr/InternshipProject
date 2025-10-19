class AlertingService
  def initialize
    @slack_webhook_url = ENV['SLACK_WEBHOOK_URL']
    @email_recipients = ENV['ALERT_EMAIL_RECIPIENTS']&.split(',') || []
  end

  def send_automation_failure_alert(execution, error)
    message = build_automation_failure_message(execution, error)
    send_slack_alert(message, :critical)
    send_email_alert("Automation Job Failure", message) if @email_recipients.any?
  end

  def send_job_failure_alert(job_name, error_message, execution_time = nil)
    message = build_job_failure_message(job_name, error_message, execution_time)
    send_slack_alert(message, :warning)
  end

  def send_high_error_rate_alert(job_name, error_rate, threshold = 10.0)
    message = build_high_error_rate_message(job_name, error_rate, threshold)
    send_slack_alert(message, :critical)
    send_email_alert("High Error Rate Alert", message) if @email_recipients.any?
  end

  def send_system_health_alert(component, status, details = {})
    message = build_system_health_message(component, status, details)
    send_slack_alert(message, status == 'down' ? :critical : :warning)
  end

  def send_resume_generation_alert(resume_id, error_message, user_id = nil)
    message = build_resume_generation_message(resume_id, error_message, user_id)
    send_slack_alert(message, :warning)
  end

  private

  def send_slack_alert(message, severity = :info)
    return unless @slack_webhook_url.present?

    payload = {
      text: message,
      username: "Resume Builder Alerts",
      icon_emoji: severity_emoji(severity),
      attachments: [
        {
          color: severity_color(severity),
          fields: [
            {
              title: "Environment",
              value: Rails.env,
              short: true
            },
            {
              title: "Timestamp",
              value: Time.current.strftime("%Y-%m-%d %H:%M:%S UTC"),
              short: true
            }
          ]
        }
      ]
    }

    begin
      HTTParty.post(@slack_webhook_url, {
        body: payload.to_json,
        headers: { 'Content-Type' => 'application/json' }
      })
    rescue => e
      Rails.logger.error "Failed to send Slack alert: #{e.message}"
    end
  end

  def send_email_alert(subject, message)
    return if @email_recipients.empty?

    @email_recipients.each do |email|
      begin
        AlertMailer.system_alert(email, subject, message).deliver_now
      rescue => e
        Rails.logger.error "Failed to send email alert to #{email}: #{e.message}"
      end
    end
  end

  def build_automation_failure_message(execution, error)
    <<~MESSAGE
      🚨 *CRITICAL: Automation Job Failure*
      
      *Job:* #{execution.job_name}
      *Execution ID:* #{execution.id}
      *Error:* #{error.message}
      *Retry Count:* #{execution.retry_count}
      *Queue:* #{execution.queue_name}
      
      This is a critical automation failure that requires immediate attention.
    MESSAGE
  end

  def build_job_failure_message(job_name, error_message, execution_time)
    <<~MESSAGE
      ⚠️ *Job Failure Alert*
      
      *Job:* #{job_name}
      *Error:* #{error_message}
      *Execution Time:* #{execution_time&.round(2)}s
      *Environment:* #{Rails.env}
      
      Please check the job execution logs for more details.
    MESSAGE
  end

  def build_high_error_rate_message(job_name, error_rate, threshold)
    <<~MESSAGE
      🚨 *HIGH ERROR RATE ALERT*
      
      *Job:* #{job_name}
      *Current Error Rate:* #{error_rate}%
      *Threshold:* #{threshold}%
      *Environment:* #{Rails.env}
      
      The error rate for this job has exceeded the acceptable threshold.
    MESSAGE
  end

  def build_system_health_message(component, status, details)
    status_emoji = status == 'down' ? '🔴' : '🟡'
    
    <<~MESSAGE
      #{status_emoji} *System Health Alert*
      
      *Component:* #{component}
      *Status:* #{status.upcase}
      *Details:* #{details.to_json}
      *Environment:* #{Rails.env}
    MESSAGE
  end

  def build_resume_generation_message(resume_id, error_message, user_id)
    <<~MESSAGE
      ⚠️ *Resume Generation Issue*
      
      *Resume ID:* #{resume_id}
      *User ID:* #{user_id || 'Unknown'}
      *Error:* #{error_message}
      *Environment:* #{Rails.env}
      
      This may indicate an issue with the resume generation service.
    MESSAGE
  end

  def severity_emoji(severity)
    case severity
    when :critical then ':rotating_light:'
    when :warning then ':warning:'
    when :info then ':information_source:'
    else ':bell:'
    end
  end

  def severity_color(severity)
    case severity
    when :critical then 'danger'
    when :warning then 'warning'
    when :info then 'good'
    else '#36a64f'
    end
  end
end
