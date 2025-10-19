class Resume < ApplicationRecord
  belongs_to :user

  validates :title, presence: true
  validates :content, presence: true
  validates :template_name, presence: true
  validates :status, inclusion: { in: %w[draft generating completed failed] }

  scope :completed, -> { where(status: 'completed') }
  scope :recent, -> { order(created_at: :desc) }
  scope :optimized, -> { where(is_optimized: true) }

  before_save :set_generation_metrics
  after_create :track_resume_creation

  def generate_pdf!
    update!(status: 'generating')
    
    start_time = Time.current
    begin
      pdf_content = ResumeGeneratorService.new(self).generate_pdf
      
      # Save PDF to file system or cloud storage
      file_path = save_pdf_file(pdf_content)
      
      update!(
        status: 'completed',
        file_path: file_path,
        generated_at: Time.current,
        generation_time_ms: ((Time.current - start_time) * 1000).to_i
      )
      
      user.track_event('resume_generated', {
        resume_id: id,
        template_name: template_name,
        generation_time_ms: generation_time_ms
      })
      
    rescue => e
      update!(
        status: 'failed',
        error_message: e.message
      )
      
      user.track_event('resume_generation_failed', {
        resume_id: id,
        error: e.message
      })
      
      raise e
    end
  end

  def optimize_for_premium!
    return unless user.premium?
    
    # Apply premium optimizations
    self.is_optimized = true
    self.metadata = metadata.merge(
      optimized_at: Time.current,
      optimization_version: '2.0'
    )
    save!
  end

  def generation_time_seconds
    return nil unless generation_time_ms
    generation_time_ms / 1000.0
  end

  def file_size
    return nil unless file_path && File.exist?(file_path)
    File.size(file_path)
  end

  private

  def set_generation_metrics
    if status_changed? && status == 'completed'
      self.generated_at ||= Time.current
    end
  end

  def track_resume_creation
    user.track_event('resume_created', {
      resume_id: id,
      template_name: template_name,
      is_premium: user.premium?
    })
  end

  def save_pdf_file(pdf_content)
    # In production, this would save to AWS S3 or similar
    directory = Rails.root.join('storage', 'resumes', user.id.to_s)
    FileUtils.mkdir_p(directory)
    
    filename = "#{id}_#{SecureRandom.hex(8)}.pdf"
    file_path = directory.join(filename)
    
    File.write(file_path, pdf_content)
    file_path.to_s
  end
end
