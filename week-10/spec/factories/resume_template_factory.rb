# Resume Template Factory for Testing
FactoryBot.define do
  factory :resume_template do
    sequence(:name) { |n| "Template #{n}" }
    sequence(:slug) { |n| "template_#{n}" }
    description { 'A professional resume template' }
    category { 'professional' }
    is_premium { false }
    is_active { true }
    
    template_config { 
      { 
        font_family: 'Arial',
        font_size: '11pt',
        primary_color: '#2c3e50',
        secondary_color: '#3498db',
        layout: 'standard'
      } 
    }
    
    avg_generation_time_ms { 2000 }
    total_generations { 100 }

    trait :premium do
      is_premium { true }
      description { 'A premium professional resume template' }
    end

    trait :inactive do
      is_active { false }
    end

    trait :creative do
      category { 'creative' }
      name { 'Creative Template' }
      template_config { 
        { 
          font_family: 'Helvetica',
          font_size: '10pt',
          primary_color: '#e74c3c',
          secondary_color: '#f39c12',
          layout: 'creative'
        } 
      }
    end

    trait :fast_generation do
      avg_generation_time_ms { 500 }
      total_generations { 10000 }
    end
  end
end

