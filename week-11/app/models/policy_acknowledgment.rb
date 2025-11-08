# Policy Acknowledgment Model
# Tracks user acknowledgments of policies

class PolicyAcknowledgment < ApplicationRecord
  belongs_to :user
  belongs_to :policy, class_name: 'PolicyMisconduct'

  validates :policy_id, uniqueness: { scope: :user_id }

  scope :recent, -> { order(acknowledged_at: :desc) }
end

