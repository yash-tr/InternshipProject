class SignalRepository
  class << self
    def fetch(user_id:, job_ids:, context:)
      metrics = AnalyticsEvent
        .where(user_id: user_id, job_id: job_ids, event_type: "job_interaction")
        .group(:job_id)
        .select(:job_id, "AVG(click_score) AS click_score", "MAX(applicant_fit) AS applicant_fit", "MAX(freshness) AS freshness")

      metrics.each_with_object(Hash.new { |h, k| h[k] = {} }) do |row, memo|
        memo[row.job_id] = {
          recent_clicks: row.click_score.to_f,
          applicant_fit: row.applicant_fit.to_f,
          freshness: row.freshness.to_f
        }
      end.tap do |result|
        job_ids.each { |job_id| result[job_id] ||= default_signal(context) }
      end
    end

    private

    def default_signal(context)
      {
        recent_clicks: context == "search" ? 0.4 : 0.2,
        applicant_fit: 0.1,
        freshness: 0.3
      }
    end
  end
end

