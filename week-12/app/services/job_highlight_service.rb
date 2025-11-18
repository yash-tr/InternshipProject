class JobHighlightService
  def initialize(repository: JobHighlightRepository)
    @repository = repository
  end

  def for_jobs(job_ids)
    @repository.for_jobs(job_ids)
  end

  def create_highlight!(job_id:, summary:, tags: [])
    highlight = @repository.create!(job_id: job_id, summary: summary, tags: tags)
    AnalyticsService.new.track(event: "job_highlight.created", properties: { job_id: job_id })
    highlight
  end

  def backfill!(batch_size:)
    Job.where(highlighted: false).limit(batch_size).find_each do |job|
      next if @repository.exists_for?(job.id)

      create_highlight!(
        job_id: job.id,
        summary: HighlightSummarizer.summarize(job),
        tags: job.tags.sample(3)
      )
    end
  end
end

