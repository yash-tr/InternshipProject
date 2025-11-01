# Resume Factory for Testing
FactoryBot.define do
  factory :resume do
    association :user
    sequence(:title) { |n| "Resume #{n}" }
    template_name { 'modern_professional' }
    status { 'draft' }
    
    personal_info { 
      { 
        phone: '123-456-7890',
        address: '123 Main St',
        linkedin: 'linkedin.com/in/user',
        github: 'github.com/user',
        website: 'user.com'
      } 
    }
    
    experience { 
      [
        {
          title: 'Software Engineer',
          company: 'Tech Corp',
          location: 'San Francisco, CA',
          start_date: '2020-01-01',
          end_date: '2023-12-31',
          current: false,
          description: 'Developed and maintained web applications',
          achievements: ['Led team of 5 developers', 'Increased performance by 40%']
        }
      ]
    }
    
    education { 
      [
        {
          degree: 'Bachelor of Science',
          institution: 'University of Technology',
          location: 'San Francisco, CA',
          graduation_date: '2019-05-01',
          gpa: '3.8',
          relevant_coursework: ['Computer Science', 'Software Engineering']
        }
      ]
    }
    
    skills { 
      [
        { name: 'Ruby on Rails', level: 'expert', category: 'Backend' },
        { name: 'React', level: 'advanced', category: 'Frontend' },
        { name: 'PostgreSQL', level: 'advanced', category: 'Database' }
      ]
    }
    
    projects { 
      [
        {
          name: 'Resume Builder Platform',
          description: 'Full-stack web application',
          technologies: ['Rails', 'React', 'PostgreSQL'],
          url: 'https://example.com',
          github_url: 'https://github.com/user/project',
          start_date: '2023-01-01',
          end_date: '2023-12-31'
        }
      ]
    }

    trait :completed do
      status { 'completed' }
      file_path { '/tmp/sample.pdf' }
      file_size { 1024 * 1024 } # 1MB
      generated_at { Time.current }
      generation_time_ms { 2500 }
    end

    trait :generating do
      status { 'generating' }
    end

    trait :failed do
      status { 'failed' }
      error_message { 'PDF generation failed' }
    end

    trait :optimized do
      is_optimized { true }
      premium_features_enabled { true }
    end

    trait :with_metadata do
      metadata { 
        { 
          version: 1,
          last_modified_by: user.id,
          changes_count: 5
        } 
      }
    end
  end
end

