class CareerMisconductPolicy
  POLICY_DOC_PATH = Rails.root.join("config", "policies", "career_misconduct.yml")

  def policy_snapshot
    @policy_snapshot ||= YAML.load_file(POLICY_DOC_PATH).deep_symbolize_keys
  end

  def active_blocks_for(user)
    UserBlock.active.where(user_id: user.id).as_json
  end

  def report_misconduct!(reporter_id:, target_id:, reason:)
    PolicyMisconduct.create!(
      reporter_id: reporter_id,
      target_id: target_id,
      reason: reason,
      policy_version: policy_snapshot[:version]
    )
  end

  def block_user!(reviewer_id:, target_id:, reason:)
    transaction do
      block = UserBlock.create!(
        reviewer_id: reviewer_id,
        user_id: target_id,
        reason: reason,
        policy_version: policy_snapshot[:version]
      )
      PolicyEnforcementWorker.perform_async(target_id)
      block
    end
  end

  def unblock_user!(reviewer_id:, target_id:)
    UserBlock.active.find_by!(user_id: target_id).tap do |block|
      block.update!(revoked_by: reviewer_id, revoked_at: Time.current)
    end
  end

  private

  def transaction(&block)
    ActiveRecord::Base.transaction(&block)
  end
end

