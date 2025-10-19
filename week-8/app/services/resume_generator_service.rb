class ResumeGeneratorService
  include ActiveSupport::Rescuable

  def initialize(resume)
    @resume = resume
    @user = resume.user
    @template = find_template(resume.template_name)
  end

  def generate_pdf
    Rails.logger.info "Generating PDF for resume #{@resume.id} with template #{@template&.name}"
    
    start_time = Time.current
    
    # Validate template availability
    validate_template_access!
    
    # Parse and structure resume data
    structured_data = parse_resume_data
    
    # Apply premium optimizations if user is premium
    if @user.premium?
      structured_data = apply_premium_optimizations(structured_data)
    end
    
    # Generate PDF content
    pdf_content = generate_pdf_content(structured_data)
    
    # Track generation metrics
    track_generation_metrics(start_time)
    
    pdf_content
  rescue => e
    Rails.logger.error "Resume generation failed for resume #{@resume.id}: #{e.message}"
    raise ResumeGenerationError, "Failed to generate resume: #{e.message}"
  end

  private

  def find_template(template_name)
    ResumeTemplate.find_by(name: template_name, is_active: true)
  end

  def validate_template_access!
    return if @template&.available_for_user?(@user)
    
    if @template&.is_premium? && !@user.premium?
      raise ResumeGenerationError, "Premium template requires premium subscription"
    end
    
    raise ResumeGenerationError, "Template not found or inactive" unless @template
  end

  def parse_resume_data
    {
      personal_info: parse_personal_info,
      experience: parse_experience,
      education: parse_education,
      skills: parse_skills,
      projects: parse_projects,
      template_config: @template.template_config
    }
  end

  def parse_personal_info
    personal_info = @resume.personal_info.is_a?(Hash) ? @resume.personal_info : {}
    
    {
      full_name: @user.full_name,
      email: @user.email,
      phone: personal_info['phone'],
      address: personal_info['address'],
      linkedin: personal_info['linkedin'],
      github: personal_info['github'],
      website: personal_info['website']
    }.compact
  end

  def parse_experience
    experience_data = @resume.experience.is_a?(Array) ? @resume.experience : []
    
    experience_data.map do |exp|
      {
        title: exp['title'],
        company: exp['company'],
        location: exp['location'],
        start_date: exp['start_date'],
        end_date: exp['end_date'],
        current: exp['current'] || false,
        description: exp['description'],
        achievements: exp['achievements'] || []
      }
    end
  end

  def parse_education
    education_data = @resume.education.is_a?(Array) ? @resume.education : []
    
    education_data.map do |edu|
      {
        degree: edu['degree'],
        institution: edu['institution'],
        location: edu['location'],
        graduation_date: edu['graduation_date'],
        gpa: edu['gpa'],
        relevant_coursework: edu['relevant_coursework'] || []
      }
    end
  end

  def parse_skills
    skills_data = @resume.skills.is_a?(Array) ? @resume.skills : []
    
    skills_data.map do |skill|
      {
        name: skill['name'],
        level: skill['level'],
        category: skill['category']
      }
    end
  end

  def parse_projects
    projects_data = @resume.projects.is_a?(Array) ? @resume.projects : []
    
    projects_data.map do |project|
      {
        name: project['name'],
        description: project['description'],
        technologies: project['technologies'] || [],
        url: project['url'],
        github_url: project['github_url'],
        start_date: project['start_date'],
        end_date: project['end_date']
      }
    end
  end

  def apply_premium_optimizations(data)
    Rails.logger.info "Applying premium optimizations for user #{@user.id}"
    
    # Enhanced formatting and styling
    data[:template_config] = data[:template_config].merge(
      premium_styling: true,
      enhanced_layout: true,
      color_scheme: @user.preferences['color_scheme'] || 'professional'
    )
    
    # AI-powered content enhancement
    if @user.preferences['ai_enhancement']
      data = enhance_content_with_ai(data)
    end
    
    # Advanced formatting options
    data[:formatting_options] = {
      font_size: @user.preferences['font_size'] || '11pt',
      line_spacing: @user.preferences['line_spacing'] || '1.15',
      margin_size: @user.preferences['margin_size'] || '0.75in'
    }
    
    data
  end

  def enhance_content_with_ai(data)
    # This would integrate with an AI service for content enhancement
    # For now, we'll simulate some basic enhancements
    
    data[:experience].each do |exp|
      if exp[:description].present?
        exp[:enhanced_description] = enhance_text(exp[:description])
      end
    end
    
    data[:projects].each do |project|
      if project[:description].present?
        project[:enhanced_description] = enhance_text(project[:description])
      end
    end
    
    data
  end

  def enhance_text(text)
    # Simulate AI enhancement - in production, this would call an AI service
    "#{text} (AI Enhanced)"
  end

  def generate_pdf_content(data)
    # Use Prawn to generate PDF
    pdf = Prawn::Document.new(
      page_size: 'A4',
      margin: [data[:formatting_options]&.dig(:margin_size) || 0.75.in, 0.75.in]
    )
    
    # Apply template-specific generation
    case @template.slug
    when 'modern_professional'
      generate_modern_professional_pdf(pdf, data)
    when 'creative_design'
      generate_creative_design_pdf(pdf, data)
    when 'minimal_clean'
      generate_minimal_clean_pdf(pdf, data)
    else
      generate_default_pdf(pdf, data)
    end
    
    pdf.render
  end

  def generate_modern_professional_pdf(pdf, data)
    # Header
    pdf.font_size 24
    pdf.text data[:personal_info][:full_name], style: :bold
    pdf.font_size 12
    pdf.text "#{data[:personal_info][:email]} | #{data[:personal_info][:phone]}"
    pdf.move_down 20
    
    # Experience
    if data[:experience].any?
      pdf.font_size 16
      pdf.text "EXPERIENCE", style: :bold
      pdf.stroke_horizontal_rule
      pdf.move_down 10
      
      data[:experience].each do |exp|
        pdf.font_size 14
        pdf.text exp[:title], style: :bold
        pdf.font_size 12
        pdf.text "#{exp[:company]} | #{exp[:location]} | #{format_date_range(exp)}"
        pdf.move_down 5
        pdf.text exp[:description] if exp[:description]
        pdf.move_down 10
      end
    end
    
    # Education
    if data[:education].any?
      pdf.font_size 16
      pdf.text "EDUCATION", style: :bold
      pdf.stroke_horizontal_rule
      pdf.move_down 10
      
      data[:education].each do |edu|
        pdf.font_size 14
        pdf.text edu[:degree], style: :bold
        pdf.font_size 12
        pdf.text "#{edu[:institution]} | #{edu[:location]} | #{edu[:graduation_date]}"
        pdf.move_down 10
      end
    end
    
    # Skills
    if data[:skills].any?
      pdf.font_size 16
      pdf.text "SKILLS", style: :bold
      pdf.stroke_horizontal_rule
      pdf.move_down 10
      
      skills_text = data[:skills].map { |skill| skill[:name] }.join(' • ')
      pdf.text skills_text
    end
  end

  def generate_creative_design_pdf(pdf, data)
    # Creative design template implementation
    generate_modern_professional_pdf(pdf, data) # Simplified for now
  end

  def generate_minimal_clean_pdf(pdf, data)
    # Minimal clean template implementation
    generate_modern_professional_pdf(pdf, data) # Simplified for now
  end

  def generate_default_pdf(pdf, data)
    # Default template implementation
    generate_modern_professional_pdf(pdf, data)
  end

  def format_date_range(experience)
    start_date = experience[:start_date]
    end_date = experience[:end_date] || (experience[:current] ? 'Present' : '')
    
    if end_date.present?
      "#{start_date} - #{end_date}"
    else
      start_date
    end
  end

  def track_generation_metrics(start_time)
    generation_time = ((Time.current - start_time) * 1000).to_i
    
    @resume.update!(
      generation_time_ms: generation_time,
      api_calls_count: @resume.api_calls_count + 1
    )
    
    # Update template performance metrics
    @template&.update_generation_time!(generation_time)
    
    # Track analytics event
    @user.track_event('resume_pdf_generated', {
      resume_id: @resume.id,
      template_name: @template&.name,
      generation_time_ms: generation_time,
      is_premium: @user.premium?
    })
  end
end

class ResumeGenerationError < StandardError; end
