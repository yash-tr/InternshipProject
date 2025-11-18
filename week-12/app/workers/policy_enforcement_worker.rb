class PolicyEnforcementWorker
  include Sidekiq::Worker
  sidekiq_options queue: :policy_enforcement, retry: 5

  def perform(user_id)
    User.transaction do
      user = User.lock(true).find(user_id)
      block = UserBlock.active.find_by(user_id: user_id)

      if block
        user.update!(blocked_at: Time.current, access_scope: "read_only")
        AuditLog.create!(event: "user_blocked", user_id: user_id, metadata: block.as_json)
      else
        user.update!(blocked_at: nil, access_scope: "full")
        AuditLog.create!(event: "user_unblocked", user_id: user_id)
      end
    end
  end
end

