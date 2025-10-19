# Create sample resume templates
puts "Creating resume templates..."

templates = [
  {
    name: 'Modern Professional',
    slug: 'modern_professional',
    description: 'A clean, modern design perfect for tech professionals',
    category: 'professional',
    is_premium: false,
    template_config: {
      font_family: 'Arial',
      color_scheme: 'blue',
      layout: 'single_column'
    },
    sections: ['personal_info', 'experience', 'education', 'skills', 'projects'],
    is_active: true
  },
  {
    name: 'Creative Design',
    slug: 'creative_design',
    description: 'A bold, creative template for designers and artists',
    category: 'creative',
    is_premium: true,
    template_config: {
      font_family: 'Helvetica',
      color_scheme: 'colorful',
      layout: 'two_column'
    },
    sections: ['personal_info', 'experience', 'education', 'skills', 'projects', 'portfolio'],
    is_active: true
  },
  {
    name: 'Minimal Clean',
    slug: 'minimal_clean',
    description: 'A minimalist template with clean lines and plenty of white space',
    category: 'minimal',
    is_premium: false,
    template_config: {
      font_family: 'Times New Roman',
      color_scheme: 'black_white',
      layout: 'single_column'
    },
    sections: ['personal_info', 'experience', 'education', 'skills'],
    is_active: true
  },
  {
    name: 'Executive Summary',
    slug: 'executive_summary',
    description: 'A sophisticated template for senior executives',
    category: 'executive',
    is_premium: true,
    template_config: {
      font_family: 'Georgia',
      color_scheme: 'dark_blue',
      layout: 'single_column'
    },
    sections: ['personal_info', 'summary', 'experience', 'education', 'skills', 'achievements'],
    is_active: true
  },
  {
    name: 'Academic Research',
    slug: 'academic_research',
    description: 'A template designed for academic and research positions',
    category: 'academic',
    is_premium: false,
    template_config: {
      font_family: 'Times New Roman',
      color_scheme: 'black_white',
      layout: 'single_column'
    },
    sections: ['personal_info', 'education', 'research', 'publications', 'skills', 'awards'],
    is_active: true
  }
]

templates.each do |template_attrs|
  template = ResumeTemplate.find_or_create_by(slug: template_attrs[:slug]) do |t|
    t.assign_attributes(template_attrs)
  end
  
  puts "Created template: #{template.name}"
end

# Create sample users
puts "Creating sample users..."

# Free user
free_user = User.find_or_create_by(email: 'free@example.com') do |user|
  user.first_name = 'John'
  user.last_name = 'Doe'
  user.password = 'password123'
  user.password_confirmation = 'password123'
  user.confirmed_at = Time.current
  user.subscription_tier = 'free'
  user.is_premium = false
end

# Premium user
premium_user = User.find_or_create_by(email: 'premium@example.com') do |user|
  user.first_name = 'Jane'
  user.last_name = 'Smith'
  user.password = 'password123'
  user.password_confirmation = 'password123'
  user.confirmed_at = Time.current
  user.subscription_tier = 'premium'
  user.is_premium = true
  user.subscription_expires_at = 1.year.from_now
  user.preferences = {
    color_scheme: 'professional',
    font_size: '11pt',
    ai_enhancement: true
  }
end

puts "Created users: #{free_user.email}, #{premium_user.email}"

# Create sample resumes
puts "Creating sample resumes..."

# Free user resume
free_resume = Resume.find_or_create_by(user: free_user, title: 'Software Developer Resume') do |resume|
  resume.template_name = 'Modern Professional'
  resume.content = 'Sample resume content for free user'
  resume.status = 'completed'
  resume.personal_info = {
    phone: '+1-555-0123',
    address: '123 Main St, City, State 12345',
    linkedin: 'linkedin.com/in/johndoe',
    github: 'github.com/johndoe'
  }
  resume.experience = [
    {
      title: 'Software Developer',
      company: 'Tech Corp',
      location: 'San Francisco, CA',
      start_date: '2020-01-01',
      end_date: '2023-12-31',
      current: false,
      description: 'Developed web applications using Ruby on Rails and React'
    }
  ]
  resume.education = [
    {
      degree: 'Bachelor of Science in Computer Science',
      institution: 'University of Technology',
      location: 'San Francisco, CA',
      graduation_date: '2019-05-01',
      gpa: '3.8'
    }
  ]
  resume.skills = [
    { name: 'Ruby on Rails', level: 'Expert', category: 'Backend' },
    { name: 'React', level: 'Advanced', category: 'Frontend' },
    { name: 'PostgreSQL', level: 'Advanced', category: 'Database' }
  ]
  resume.generated_at = 1.day.ago
  resume.generation_time_ms = 2500
end

# Premium user resume
premium_resume = Resume.find_or_create_by(user: premium_user, title: 'Senior Software Engineer Resume') do |resume|
  resume.template_name = 'Creative Design'
  resume.content = 'Sample resume content for premium user'
  resume.status = 'completed'
  resume.is_optimized = true
  resume.personal_info = {
    phone: '+1-555-0456',
    address: '456 Oak Ave, City, State 12345',
    linkedin: 'linkedin.com/in/janesmith',
    github: 'github.com/janesmith',
    website: 'janesmith.dev'
  }
  resume.experience = [
    {
      title: 'Senior Software Engineer',
      company: 'Innovation Labs',
      location: 'New York, NY',
      start_date: '2021-01-01',
      end_date: nil,
      current: true,
      description: 'Lead development of scalable web applications and mentor junior developers'
    },
    {
      title: 'Software Engineer',
      company: 'StartupXYZ',
      location: 'New York, NY',
      start_date: '2019-06-01',
      end_date: '2020-12-31',
      current: false,
      description: 'Built and maintained full-stack web applications'
    }
  ]
  resume.education = [
    {
      degree: 'Master of Science in Computer Science',
      institution: 'Columbia University',
      location: 'New York, NY',
      graduation_date: '2019-05-01',
      gpa: '3.9'
    }
  ]
  resume.skills = [
    { name: 'Ruby on Rails', level: 'Expert', category: 'Backend' },
    { name: 'React', level: 'Expert', category: 'Frontend' },
    { name: 'PostgreSQL', level: 'Expert', category: 'Database' },
    { name: 'AWS', level: 'Advanced', category: 'Cloud' },
    { name: 'Docker', level: 'Advanced', category: 'DevOps' }
  ]
  resume.projects = [
    {
      name: 'E-commerce Platform',
      description: 'Built a scalable e-commerce platform serving 100k+ users',
      technologies: ['Ruby on Rails', 'React', 'PostgreSQL', 'Redis'],
      github_url: 'github.com/janesmith/ecommerce-platform'
    }
  ]
  resume.generated_at = 2.hours.ago
  resume.generation_time_ms = 1800
end

puts "Created sample resumes"

# Create sample analytics events
puts "Creating sample analytics events..."

# Generate some sample events for the past week
7.times do |i|
  date = i.days.ago
  
  # User login events
  [free_user, premium_user].each do |user|
    AnalyticsEvent.create!(
      user: user,
      event_name: 'user_login',
      event_category: 'authentication',
      properties: { login_method: 'email' },
      occurred_at: date.beginning_of_day + rand(24).hours
    )
  end
  
  # Resume generation events
  if i < 5 # Only for last 5 days
    AnalyticsEvent.create!(
      user: free_user,
      event_name: 'resume_generation_started',
      event_category: 'resume',
      properties: { template_name: 'Modern Professional' },
      occurred_at: date.beginning_of_day + rand(24).hours
    )
    
    AnalyticsEvent.create!(
      user: premium_user,
      event_name: 'resume_generation_started',
      event_category: 'resume',
      properties: { template_name: 'Creative Design' },
      occurred_at: date.beginning_of_day + rand(24).hours
    )
  end
end

puts "Created sample analytics events"

# Create sample job executions
puts "Creating sample job executions..."

# Create some successful job executions
5.times do |i|
  JobExecution.create!(
    job_name: 'AutomationJob',
    status: 'completed',
    success: true,
    started_at: i.days.ago + 2.hours,
    completed_at: i.days.ago + 2.hours + 30.seconds,
    execution_time_ms: 30000 + rand(10000),
    queue_name: 'automation'
  )
end

# Create some failed job executions
2.times do |i|
  JobExecution.create!(
    job_name: 'ResumeGenerationJob',
    status: 'failed',
    success: false,
    started_at: i.days.ago + 1.hour,
    completed_at: i.days.ago + 1.hour + 5.seconds,
    execution_time_ms: 5000,
    error_message: 'Template not found',
    queue_name: 'resume_generation'
  )
end

puts "Created sample job executions"

puts "Seed data creation completed!"
puts "Free user: free@example.com / password123"
puts "Premium user: premium@example.com / password123"
