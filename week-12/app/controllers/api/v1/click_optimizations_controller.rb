module Api
  module V1
    class ClickOptimizationsController < ApplicationController
      def create
        payload = ClickOptimizationService.new.rank!(
          user_id: current_user.id,
          job_ids: params.require(:job_ids),
          context: params[:context]
        )

        render json: payload, status: :ok
      end
    end
  end
end

