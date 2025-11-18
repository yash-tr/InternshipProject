class JobHighlight < ApplicationRecord
  scope :for_jobs, ->(job_ids) { where(job_id: job_ids) }

  serialize :tags, Array

  validates :job_id, :summary, presence: true
end

