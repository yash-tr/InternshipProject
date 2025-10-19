class ResumeGenerationJob < ApplicationJob
  queue_as :resume_generation
  retry_on ResumeGenerationError, wait: :exponentially_longer, attempts: 3
  retry_on StandardError, wait: :exponentially_longer, attempts: 2

  def perform(resume_id)
    resume = Resume.find(resume_id)
    
    execution = JobExecution.create!(
      job_name: 'ResumeGenerationJob',
      status: 'pending',
      parameters: { resume_id: resume_id },
      queue_name: 'resume_generation'
    )

    execution.mark_as_started!

    begin
      Rails.logger.info "Starting resume generation for resume #{resume_id}"
      
      # Generate the PDF
      pdf_content = ResumeGeneratorService.new(resume).generate_pdf
      
      # Save the PDF file
      file_path = save_pdf_file(resume, pdf_content)
      
      # Update resume with success status
      resume.update!(
        status: 'completed',
        file_path: file_path,
        generated_at: Time.current
      )
      
      # Track successful generation
      resume.user.track_event('resume_generation_completed', {
        resume_id: resume.id,
        template_name: resume.template_name,
        generation_time_ms: resume.generation_time_ms
      })
      
      execution.mark_as_completed!({
        resume_id: resume_id,
        file_path: file_path,
        generation_time_ms: resume.generation_time_ms
      })
      
      Rails.logger.info "Resume generation completed for resume #{resume_id}"
      
    rescue ResumeGenerationError => e
      Rails.logger.error "Resume generation failed for resume #{resume_id}: #{e.message}"
      
      resume.update!(
        status: 'failed',
        error_message: e.message
      )
      
      execution.mark_as_failed!(e.message)
      
      # Send alert for resume generation failures
      AlertingService.new.send_resume_generation_alert(resume_id, e.message, resume.user_id)
      
      raise e
      
    rescue => e
      Rails.logger.error "Unexpected error in resume generation for resume #{resume_id}: #{e.message}"
      
      resume.update!(
        status: 'failed',
        error_message: "Unexpected error: #{e.message}"
      )
      
      execution.mark_as_failed!(e.message)
      
      # Send alert for unexpected errors
      AlertingService.new.send_resume_generation_alert(resume_id, e.message, resume.user_id)
      
      raise e
    end
  end

  private

  def save_pdf_file(resume, pdf_content)
    # Create directory structure
    directory = Rails.root.join('storage', 'resumes', resume.user_id.to_s)
    FileUtils.mkdir_p(directory)
    
    # Generate unique filename
    filename = "#{resume.id}_#{SecureRandom.hex(8)}.pdf"
    file_path = directory.join(filename)
    
    # Write PDF content to file
    File.write(file_path, pdf_content)
    
    # Return the file path as string
    file_path.to_s
  end
end
