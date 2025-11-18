class ClickOptimizationService
  def initialize(rank_client: ClickOptimizationRanker.new, metrics: AnalyticsService.new)
    @rank_client = rank_client
    @metrics = metrics
  end

  def rank!(user_id:, job_ids:, context: nil)
    raise ArgumentError, "job_ids required" if job_ids.blank?

    ranked = @rank_client.rank(user_id: user_id, job_ids: job_ids, context: context)
    @metrics.track(
      event: "click_optimization.rank",
      user_id: user_id,
      properties: { job_count: job_ids.count, context: context }
    )

    { job_ids: ranked, impression_token: SecureRandom.uuid }
  end
end

