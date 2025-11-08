# Flag Model
# Represents flags raised by recruiters/admins for policy violations

class Flag < ApplicationRecord
  belongs_to :flagged_by, class_name: 'User'
  belongs_to :flagged_entity, polymorphic: true
  belongs_to :resolved_by, class_name: 'User', optional: true

  # Violation types
  VIOLATION_TYPES = %w[
    spam
    inappropriate_content
    fake_information
    harassment
    copyright_violation
    privacy_violation
    other
  ].freeze

  # Severity levels
  SEVERITIES = %w[low medium high critical].freeze

  # Statuses
  STATUSES = %w[pending under_review resolved rejected].freeze

  validates :violation_type, inclusion: { in: VIOLATION_TYPES }
  validates :severity, inclusion: { in: SEVERITIES }
  validates :status, inclusion: { in: STATUSES }
  validates :reason, presence: true
  validates :flagged_entity_type, presence: true
  validates :flagged_entity_id, presence: true

  scope :pending, -> { where(status: 'pending') }
  scope :resolved, -> { where(status: 'resolved') }
  scope :by_severity, ->(severity) { where(severity: severity) }
  scope :critical, -> { where(severity: 'critical') }
  scope :high_priority, -> { where(severity: ['high', 'critical']) }

  # Check if flag is resolved
  def resolved?
    status == 'resolved'
  end

  # Check if flag is pending
  def pending?
    status == 'pending'
  end

  # Auto-escalate critical flags
  after_create :auto_escalate_critical

  private

  def auto_escalate_critical
    if severity == 'critical'
      # Automatically escalate to highest priority
      update_column(:status, 'under_review')
      # Send immediate notification
      AdminNotificationService.new.notify_critical_flag(self)
    end
  end
end

