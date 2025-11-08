# User Block Model
# Represents blocked users and blocking history

class UserBlock < ApplicationRecord
  belongs_to :user
  belongs_to :blocked_by, class_name: 'User'
  belongs_to :unblocked_by, class_name: 'User', optional: true

  # Block types
  BLOCK_TYPES = %w[full partial job_portal messaging].freeze

  # Statuses
  STATUSES = %w[active expired unblocked].freeze

  validates :block_type, inclusion: { in: BLOCK_TYPES }
  validates :status, inclusion: { in: STATUSES }
  validates :reason, presence: true

  scope :active, -> { where(status: 'active') }
  scope :expired, -> { where('expires_at < ?', Time.current) }
  scope :full_blocks, -> { where(block_type: 'full') }

  # Check if block is active
  def active?
    status == 'active' && (expires_at.nil? || expires_at > Time.current)
  end

  # Check if block is expired
  def expired?
    expires_at.present? && expires_at < Time.current
  end

  # Auto-expire blocks
  after_find :check_expiration

  private

  def check_expiration
    if expired? && status == 'active'
      update_column(:status, 'expired')
    end
  end
end

