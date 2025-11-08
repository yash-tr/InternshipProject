# Policy Misconduct Report Model
# Reports of policy violations by users

class PolicyMisconductReport < ApplicationRecord
  belongs_to :reported_by, class_name: 'User'
  belongs_to :policy, class_name: 'PolicyMisconduct'

  # Violation types
  VIOLATION_TYPES = %w[
    spam
    harassment
    inappropriate_content
    fake_information
    other
  ].freeze

  # Statuses
  STATUSES = %w[pending under_review resolved rejected].freeze

  validates :violation_type, inclusion: { in: VIOLATION_TYPES }
  validates :status, inclusion: { in: STATUSES }
  validates :description, presence: true

  scope :pending, -> { where(status: 'pending') }
  scope :by_violation_type, ->(type) { where(violation_type: type) }
end

