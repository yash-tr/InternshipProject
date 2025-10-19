class Api::V1::ResumesController < ApplicationController
  before_action :authenticate_user!
  before_action :set_resume, only: [:show, :update, :destroy, :generate_pdf, :download, :optimize, :regenerate]

  def index
    @resumes = current_user.resumes.recent
                          .page(params[:page])
                          .per(params[:per_page] || 10)
    
    render json: {
      success: true,
      resumes: @resumes.map { |resume| resume_serializer(resume) },
      pagination: {
        current_page: @resumes.current_page,
        total_pages: @resumes.total_pages,
        total_count: @resumes.total_count,
        per_page: @resumes.limit_value
      }
    }
  end

  def show
    render json: {
      success: true,
      resume: resume_serializer(@resume)
    }
  end

  def create
    @resume = current_user.resumes.build(resume_params)
    
    # Check quota for free users
    unless current_user.can_generate_resume?
      return render json: {
        success: false,
        error: 'Resume generation quota exceeded. Please upgrade to premium for unlimited resumes.'
      }, status: :forbidden
    end
    
    if @resume.save
      # Track resume creation
      current_user.track_event('resume_created', {
        resume_id: @resume.id,
        template_name: @resume.template_name
      })
      
      render json: {
        success: true,
        resume: resume_serializer(@resume)
      }, status: :created
    else
      render json: {
        success: false,
        errors: @resume.errors.full_messages
      }, status: :unprocessable_entity
    end
  end

  def update
    if @resume.update(resume_params)
      render json: {
        success: true,
        resume: resume_serializer(@resume)
      }
    else
      render json: {
        success: false,
        errors: @resume.errors.full_messages
      }, status: :unprocessable_entity
    end
  end

  def destroy
    @resume.destroy
    
    # Track resume deletion
    current_user.track_event('resume_deleted', {
      resume_id: @resume.id,
      template_name: @resume.template_name
    })
    
    render json: {
      success: true,
      message: 'Resume deleted successfully'
    }
  end

  def generate_pdf
    if @resume.status == 'generating'
      return render json: {
        success: false,
        error: 'Resume is already being generated'
      }, status: :conflict
    end
    
    begin
      # Generate PDF asynchronously for better performance
      ResumeGenerationJob.perform_later(@resume.id)
      
      @resume.update!(status: 'generating')
      
      # Track generation start
      current_user.track_event('resume_generation_started', {
        resume_id: @resume.id,
        template_name: @resume.template_name
      })
      
      render json: {
        success: true,
        message: 'Resume generation started',
        status: 'generating'
      }
    rescue => e
      Rails.logger.error "Failed to start resume generation: #{e.message}"
      
      render json: {
        success: false,
        error: 'Failed to start resume generation'
      }, status: :internal_server_error
    end
  end

  def download
    if @resume.status != 'completed' || @resume.file_path.blank?
      return render json: {
        success: false,
        error: 'Resume not ready for download'
      }, status: :not_found
    end
    
    unless File.exist?(@resume.file_path)
      return render json: {
        success: false,
        error: 'Resume file not found'
      }, status: :not_found
    end
    
    # Track download
    current_user.track_event('resume_downloaded', {
      resume_id: @resume.id,
      template_name: @resume.template_name,
      file_size: @resume.file_size
    })
    
    send_file @resume.file_path, 
              filename: "#{@resume.title.parameterize}.pdf",
              type: 'application/pdf',
              disposition: 'attachment'
  end

  def optimize
    unless current_user.premium?
      return render json: {
        success: false,
        error: 'Premium subscription required for optimization'
      }, status: :forbidden
    end
    
    if @resume.optimize_for_premium!
      render json: {
        success: true,
        message: 'Resume optimized for premium features',
        resume: resume_serializer(@resume)
      }
    else
      render json: {
        success: false,
        error: 'Failed to optimize resume'
      }, status: :unprocessable_entity
    end
  end

  def regenerate
    if @resume.status == 'generating'
      return render json: {
        success: false,
        error: 'Resume is already being generated'
      }, status: :conflict
    end
    
    # Reset status and regenerate
    @resume.update!(status: 'draft')
    ResumeGenerationJob.perform_later(@resume.id)
    
    # Track regeneration
    current_user.track_event('resume_regeneration_started', {
      resume_id: @resume.id,
      template_name: @resume.template_name
    })
    
    render json: {
      success: true,
      message: 'Resume regeneration started',
      status: 'generating'
    }
  end

  def analytics
    analytics_data = {
      total_resumes: current_user.resumes.count,
      completed_resumes: current_user.resumes.completed.count,
      failed_resumes: current_user.resumes.where(status: 'failed').count,
      quota_remaining: current_user.resume_generation_quota_remaining,
      is_premium: current_user.premium?,
      recent_activity: current_user.resumes.recent.limit(5).map { |r| resume_serializer(r) }
    }
    
    render json: {
      success: true,
      analytics: analytics_data
    }
  end

  def recent
    @resumes = current_user.resumes.recent.limit(10)
    
    render json: {
      success: true,
      resumes: @resumes.map { |resume| resume_serializer(resume) }
    }
  end

  private

  def set_resume
    @resume = current_user.resumes.find(params[:id])
  end

  def resume_params
    params.require(:resume).permit(
      :title, :content, :template_name, :status,
      personal_info: {},
      experience: [],
      education: [],
      skills: [],
      projects: [],
      metadata: {}
    )
  end

  def resume_serializer(resume)
    {
      id: resume.id,
      title: resume.title,
      template_name: resume.template_name,
      status: resume.status,
      personal_info: resume.personal_info,
      experience: resume.experience,
      education: resume.education,
      skills: resume.skills,
      projects: resume.projects,
      metadata: resume.metadata,
      is_optimized: resume.is_optimized,
      generation_time_ms: resume.generation_time_ms,
      generation_time_seconds: resume.generation_time_seconds,
      file_size: resume.file_size,
      generated_at: resume.generated_at,
      created_at: resume.created_at,
      updated_at: resume.updated_at
    }
  end
end
