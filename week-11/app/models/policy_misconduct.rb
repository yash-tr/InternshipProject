# Policy Misconduct Model
# Represents platform policies and misconduct rules

class PolicyMisconduct < ApplicationRecord
  has_many :policy_acknowledgments, dependent: :destroy
  has_many :policy_misconduct_reports, dependent: :destroy

  # Severity levels
  SEVERITY_LEVELS = %w[info warning error critical].freeze

  validates :version, presence: true, uniqueness: true
  validates :title, presence: true
  validates :content, presence: true
  validates :severity_level, inclusion: { in: SEVERITY_LEVELS }

  scope :active, -> { where(is_active: true) }
  scope :current, -> { active.order(version: :desc).first }

  # Get current active policy
  def self.current_policy
    current || create_default_policy
  end

  # Check if policy requires acknowledgment
  def requires_acknowledgment?
    requires_acknowledgment && is_active
  end

  # Create default policy if none exists
  def self.create_default_policy
    create!(
      version: '1.0.0',
      title: 'Platform Usage Policy',
      content: 'Default platform policy content...',
      severity_level: 'info',
      requires_acknowledgment: false,
      is_active: true
    )
  end
end

