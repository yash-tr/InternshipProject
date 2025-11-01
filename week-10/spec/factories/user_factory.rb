# User Factory for Testing
FactoryBot.define do
  factory :user do
    sequence(:email) { |n| "user#{n}@example.com" }
    password { 'password123' }
    password_confirmation { 'password123' }
    first_name { 'John' }
    last_name { 'Doe' }
    subscription_tier { 'free' }
    is_premium { false }
    subscription_expires_at { nil }
    
    trait :premium do
      subscription_tier { 'premium' }
      is_premium { true }
      subscription_expires_at { 30.days.from_now }
    end

    trait :enterprise do
      subscription_tier { 'enterprise' }
      is_premium { true }
      subscription_expires_at { 1.year.from_now }
    end

    trait :with_preferences do
      preferences { 
        { 
          color_scheme: 'professional',
          font_size: '11pt',
          ai_enhancement: true 
        } 
      }
    end

    trait :confirmed do
      confirmed_at { Time.current }
    end
  end
end

