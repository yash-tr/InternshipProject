class User < ApplicationRecord
  devise :database_authenticatable, :registerable,
         :recoverable, :rememberable, :validatable,
         :confirmable, :trackable

  has_many :resumes, dependent: :destroy
  has_many :analytics_events, dependent: :destroy

  validates :first_name, presence: true
  validates :last_name, presence: true
  validates :subscription_tier, inclusion: { in: %w[free premium enterprise] }

  scope :premium, -> { where(is_premium: true) }
  scope :active, -> { where('subscription_expires_at > ? OR subscription_expires_at IS NULL', Time.current) }

  def full_name
    "#{first_name} #{last_name}"
  end

  def premium?
    is_premium && (subscription_expires_at.nil? || subscription_expires_at > Time.current)
  end

  def can_generate_resume?
    return true if premium?
    
    # Free users have limits
    resumes.where('created_at > ?', 1.month.ago).count < 3
  end

  def resume_generation_quota_remaining
    return Float::INFINITY if premium?
    
    3 - resumes.where('created_at > ?', 1.month.ago).count
  end

  def track_event(event_name, properties = {})
    analytics_events.create!(
      event_name: event_name,
      event_category: 'user_action',
      properties: properties,
      occurred_at: Time.current
    )
  end
end
