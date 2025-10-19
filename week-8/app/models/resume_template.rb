class ResumeTemplate < ApplicationRecord
  validates :name, presence: true
  validates :slug, presence: true, uniqueness: true
  validates :category, presence: true
  validates :is_active, inclusion: { in: [true, false] }

  scope :active, -> { where(is_active: true) }
  scope :premium, -> { where(is_premium: true) }
  scope :free, -> { where(is_premium: false) }
  scope :by_category, ->(category) { where(category: category) }

  def self.popular_templates(limit = 10)
    active.order(usage_count: :desc).limit(limit)
  end

  def self.fastest_templates(limit = 10)
    active.where.not(generation_time_avg: nil)
          .order(:generation_time_avg)
          .limit(limit)
  end

  def increment_usage!
    increment!(:usage_count)
  end

  def update_generation_time!(time_ms)
    if generation_time_avg.nil?
      update!(generation_time_avg: time_ms)
    else
      # Calculate rolling average
      new_avg = (generation_time_avg + time_ms) / 2.0
      update!(generation_time_avg: new_avg)
    end
  end

  def sections_list
    sections.is_a?(Array) ? sections : []
  end

  def config_value(key)
    template_config.is_a?(Hash) ? template_config[key] : nil
  end

  def available_for_user?(user)
    return true unless is_premium?
    user&.premium?
  end
end
