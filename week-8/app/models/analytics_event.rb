class AnalyticsEvent < ApplicationRecord
  belongs_to :user, optional: true

  validates :event_name, presence: true
  validates :event_category, presence: true
  validates :occurred_at, presence: true

  scope :recent, -> { order(occurred_at: :desc) }
  scope :by_category, ->(category) { where(event_category: category) }
  scope :by_event_name, ->(name) { where(event_name: name) }
  scope :in_timeframe, ->(start_time, end_time) { where(occurred_at: start_time..end_time) }

  def self.track(event_name, user: nil, properties: {}, session_id: nil, request: nil)
    create!(
      event_name: event_name,
      event_category: 'user_action',
      user: user,
      properties: properties,
      session_id: session_id,
      ip_address: request&.remote_ip,
      user_agent: request&.user_agent,
      referrer: request&.referer,
      page_url: request&.url,
      occurred_at: Time.current
    )
  end

  def self.event_counts_by_name(days = 7)
    in_timeframe(days.days.ago, Time.current)
      .group(:event_name)
      .count
  end

  def self.event_counts_by_category(days = 7)
    in_timeframe(days.days.ago, Time.current)
      .group(:event_category)
      .count
  end

  def self.user_retention_events(days = 7)
    in_timeframe(days.days.ago, Time.current)
      .where(event_name: ['user_signup', 'user_login', 'resume_created'])
      .group(:user_id, :event_name)
      .count
  end

  def self.conversion_funnel_events
    where(event_name: ['page_view', 'resume_started', 'resume_completed', 'resume_downloaded'])
      .group(:event_name)
      .count
  end
end
