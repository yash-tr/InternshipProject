class JobHighlightRepository
  class << self
    def for_jobs(job_ids)
      JobHighlight.for_jobs(job_ids).map do |highlight|
        highlight.as_json(only: %i[job_id summary tags score]).merge(updated_at: highlight.updated_at)
      end
    end

    def create!(job_id:, summary:, tags:)
      JobHighlight.create!(
        job_id: job_id,
        summary: summary,
        tags: tags,
        score: tags.length
      )
    end

    def exists_for?(job_id)
      JobHighlight.exists?(job_id: job_id)
    end
  end
end

