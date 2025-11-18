class HighlightSummarizer
  def self.summarize(job)
    [
      job.title,
      job.company_name,
      job.key_requirements.take(2)
    ].flatten.compact.join(" • ")
  end
end

