module Api
  module V1
    class JobTagsController < ApplicationController
      before_action :load_service

      def index
        render json: { tags: @service.renderable_tags(current_user) }
      end

      def update
        @service.persist_user_preferences!(current_user, tags_params[:preferred_tags])
        head :no_content
      end

      def rollout
        result = @service.rollout_to_all_users!
        render json: result, status: :accepted
      end

      private

      def load_service
        @service = JobTagsRolloutService.new
      end

      def tags_params
        params.require(:job_tags).permit(preferred_tags: [])
      end
    end
  end
end

