class ClickOptimizationRanker
  SIGNAL_WEIGHTS = {
    recent_clicks: 0.5,
    applicant_fit: 0.3,
    freshness: 0.2
  }.freeze

  def rank(user_id:, job_ids:, context: nil)
    scores = job_ids.index_with { |job_id| base_score(job_id) }
    signals = fetch_signals(user_id, job_ids, context)

    scores.each_key do |job_id|
      scores[job_id] += SIGNAL_WEIGHTS.sum do |key, weight|
        weight * signals.dig(job_id, key).to_f
      end
    end

    scores.sort_by { |_job_id, score| -score }.map(&:first)
  end

  private

  def fetch_signals(user_id, job_ids, context)
    SignalRepository.fetch(user_id: user_id, job_ids: job_ids, context: context)
  end

  def base_score(job_id)
    1.0 + (job_id.to_i % 10) / 100.0
  end
end

