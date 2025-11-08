# User Blocker Controller
# Handles blocking/unblocking users for policy violations

class Api::V1::UserBlockerController < ApplicationController
  before_action :authenticate_user!
  before_action :authorize_admin!

  # Block a user
  def block
    user = User.find(params[:user_id])
    reason = params[:reason] || 'Policy violation'
    duration = params[:duration] # in days, nil for permanent

    blocker = UserBlockerService.new(user, current_user)

    result = blocker.block(
      reason: reason,
      duration: duration,
      block_type: params[:block_type] || 'full',
      flag_id: params[:flag_id]
    )

    if result[:success]
      # Track analytics event
      track_blocking_event('user_blocked', user, result)

      render json: {
        success: true,
        message: 'User blocked successfully',
        block: result[:block]
      }
    else
      render json: {
        success: false,
        error: result[:error]
      }, status: :unprocessable_entity
    end
  end

  # Unblock a user
  def unblock
    user = User.find(params[:user_id])
    blocker = UserBlockerService.new(user, current_user)

    result = blocker.unblock(reason: params[:reason])

    if result[:success]
      track_blocking_event('user_unblocked', user, result)

      render json: {
        success: true,
        message: 'User unblocked successfully'
      }
    else
      render json: {
        success: false,
        error: result[:error]
      }, status: :unprocessable_entity
    end
  end

  # Check if user is blocked
  def check
    user = User.find(params[:user_id])
    block_status = UserBlockerService.new(user).check_block_status

    render json: {
      success: true,
      is_blocked: block_status[:is_blocked],
      block: block_status[:block],
      can_access_job_portal: !block_status[:is_blocked] || block_status[:block]&.block_type != 'full'
    }
  end

  # Get blocked users list
  def index
    blocked_users = UserBlock.includes(:user, :blocked_by)
                             .where(status: 'active')
                             .order(created_at: :desc)
                             .page(params[:page])
                             .per(params[:per_page] || 20)

    render json: {
      success: true,
      blocked_users: blocked_users.map { |block| block_serializer(block) },
      pagination: {
        current_page: blocked_users.current_page,
        total_pages: blocked_users.total_pages,
        total_count: blocked_users.total_count
      }
    }
  end

  # Get block history for a user
  def history
    user = User.find(params[:user_id])
    blocks = UserBlock.includes(:blocked_by)
                      .where(user: user)
                      .order(created_at: :desc)
                      .page(params[:page])
                      .per(params[:per_page] || 10)

    render json: {
      success: true,
      blocks: blocks.map { |block| block_serializer(block) },
      pagination: {
        current_page: blocks.current_page,
        total_pages: blocks.total_pages,
        total_count: blocks.total_count
      }
    }
  end

  private

  def authorize_admin!
    unless current_user.admin?
      render json: {
        success: false,
        error: 'Unauthorized. Admin access required.'
      }, status: :forbidden
    end
  end

  def track_blocking_event(event_name, user, result)
    AnalyticsService.track_event(current_user, event_name, {
      user_id: user.id,
      block_type: result[:block]&.block_type,
      reason: result[:block]&.reason,
      duration: result[:block]&.duration_days
    })
  end

  def block_serializer(block)
    {
      id: block.id,
      user: {
        id: block.user.id,
        name: block.user.full_name,
        email: block.user.email
      },
      block_type: block.block_type,
      reason: block.reason,
      status: block.status,
      blocked_by: {
        id: block.blocked_by.id,
        name: block.blocked_by.full_name
      },
      blocked_at: block.created_at,
      expires_at: block.expires_at,
      duration_days: block.duration_days,
      unblocked_at: block.unblocked_at,
      unblocked_by: block.unblocked_by ? {
        id: block.unblocked_by.id,
        name: block.unblocked_by.full_name
      } : nil
    }
  end
end

