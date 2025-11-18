module Api
  module V1
    class JobHighlightsController < ApplicationController
      before_action :highlight_service
      before_action :ensure_admin!, only: %i[create backfill]

      def index
        render json: { highlights: highlight_service.for_jobs(params[:job_ids]) }
      end

      def create
        highlight = highlight_service.create_highlight!(
          job_id: params.require(:job_id),
          summary: params.require(:summary),
          tags: params[:tags] || []
        )
        render json: highlight, status: :created
      end

      def backfill
        JobHighlightWorker.perform_async(params[:batch_size].presence || 100)
        render json: { status: "scheduled" }, status: :accepted
      end

      private

      def ensure_admin!
        head :forbidden unless current_user.admin?
      end

      def highlight_service
        @highlight_service ||= JobHighlightService.new
      end
    end
  end
end

