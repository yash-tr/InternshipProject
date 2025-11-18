class JobTagsRolloutService
  FLAG_KEY = "job_tags_global_rollout".freeze

  def renderable_tags(user)
    ensure_rollout!
    TagRepository.for_user(user.id)
  end

  def persist_user_preferences!(user, tags)
    ensure_rollout!
    TagRepository.save_preferences(user.id, tags)
  end

  def rollout_to_all_users!
    FeatureFlag.delete(FLAG_KEY)
    migrate_unknown_users
  end

  private

  def ensure_rollout!
    rollout_to_all_users! if FeatureFlag.enabled?(FLAG_KEY)
  end

  def migrate_unknown_users
    User.where(job_tags_state: nil).in_batches(of: 5_000) do |batch|
      batch.update_all(job_tags_state: "migrated")
    end
    { migrated_users: User.where(job_tags_state: "migrated").count }
  end
end

