class BlockStateRepairWorker
  include Sidekiq::Worker
  sidekiq_options queue: :policy_enforcement, retry: 2

  def perform(user_id)
    User.transaction do
      user = User.lock("FOR UPDATE").find(user_id)
      pending = PendingAction.where(user_id: user_id, completed_at: nil).exists?
      block = UserBlock.active.find_by(user_id: user_id)

      if pending && block
        return
      elsif !pending && block
        block.update!(auto_reconciled_at: Time.current)
        PolicyEnforcementWorker.perform_async(user_id)
      end
    end
  end
end

