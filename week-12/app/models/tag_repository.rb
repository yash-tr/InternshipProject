class TagRepository
  class << self
    def for_user(user_id)
      Rails.cache.fetch(cache_key(user_id), expires_in: 15.minutes) do
        JobTag.where(user_id: user_id).pluck(:label)
      end
    end

    def save_preferences(user_id, tags)
      JobTag.transaction do
        JobTag.where(user_id: user_id).delete_all
        tags.each { |tag| JobTag.create!(user_id: user_id, label: tag) }
      end
      Rails.cache.delete(cache_key(user_id))
    end

    private

    def cache_key(user_id)
      "job_tags/#{user_id}"
    end
  end
end

