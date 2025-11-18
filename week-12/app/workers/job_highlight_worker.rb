class JobHighlightWorker
  include Sidekiq::Worker
  sidekiq_options queue: :highlights, retry: 3

  def perform(batch_size = 100)
    JobHighlightService.new.backfill!(batch_size: batch_size)
  rescue => e
    Rails.logger.error("[JobHighlightWorker] #{e.class}: #{e.message}")
    raise e
  end
end

