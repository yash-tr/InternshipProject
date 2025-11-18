module Api
  module V1
    class CareerMisconductsController < ApplicationController
      before_action :ensure_admin!, only: %i[block unblock]
      before_action :policy_module

      def index
        render json: {
          policy: policy_module.policy_snapshot,
          blocks: policy_module.active_blocks_for(current_user)
        }
      end

      def create
        report = policy_module.report_misconduct!(
          reporter_id: current_user.id,
          target_id: params.require(:target_id),
          reason: params.require(:reason)
        )
        render json: report, status: :created
      end

      def block
        result = policy_module.block_user!(
          reviewer_id: current_user.id,
          target_id: params.require(:target_id),
          reason: params[:reason]
        )
        render json: result, status: :accepted
      end

      def unblock
        policy_module.unblock_user!(
          reviewer_id: current_user.id,
          target_id: params.require(:target_id)
        )
        head :no_content
      end

      private

      def ensure_admin!
        head :forbidden unless current_user.admin?
      end

      def policy_module
        @policy_module ||= CareerMisconductPolicy.new
      end
    end
  end
end

