# User Blocker Service
# Handles user blocking and unblocking logic

class UserBlockerService
  def initialize(user, blocked_by = nil)
    @user = user
    @blocked_by = blocked_by
  end

  # Block a user
  def block(reason:, duration: nil, block_type: 'full', flag_id: nil)
    # Check if user is already blocked
    existing_block = @user.user_blocks.active.first
    if existing_block
      return {
        success: false,
        error: 'User is already blocked'
      }
    end

    # Calculate expiry date
    expires_at = duration ? duration.days.from_now : nil

    # Create block
    block = @user.user_blocks.create!(
      blocked_by: @blocked_by,
      block_type: block_type,
      reason: reason,
      expires_at: expires_at,
      duration_days: duration,
      flag_id: flag_id,
      status: 'active'
    )

    # Update user status
    update_user_status(block_type)

    # Log blocking action
    log_blocking_action(block)

    {
      success: true,
      block: block
    }
  rescue => e
    Rails.logger.error "Error blocking user: #{e.message}"
    {
      success: false,
      error: e.message
    }
  end

  # Unblock a user
  def unblock(reason: nil)
    active_block = @user.user_blocks.active.first

    unless active_block
      return {
        success: false,
        error: 'User is not blocked'
      }
    end

    # Update block status
    active_block.update!(
      status: 'unblocked',
      unblocked_by: @blocked_by,
      unblocked_at: Time.current,
      unblock_reason: reason
    )

    # Restore user status
    restore_user_status

    # Log unblocking action
    log_unblocking_action(active_block)

    {
      success: true,
      block: active_block
    }
  rescue => e
    Rails.logger.error "Error unblocking user: #{e.message}"
    {
      success: false,
      error: e.message
    }
  end

  # Check block status
  def check_block_status
    active_block = @user.user_blocks.active.first

    {
      is_blocked: active_block.present?,
      block: active_block
    }
  end

  # Check if user can access job portal
  def can_access_job_portal?
    block_status = check_block_status
    return true unless block_status[:is_blocked]

    block = block_status[:block]
    block.block_type != 'full' && block.block_type != 'job_portal'
  end

  private

  def update_user_status(block_type)
    case block_type
    when 'full'
      @user.update!(is_blocked: true, blocked_reason: 'Full account block')
    when 'job_portal'
      @user.update!(job_portal_access: false)
    end
  end

  def restore_user_status
    @user.update!(
      is_blocked: false,
      blocked_reason: nil,
      job_portal_access: true
    )
  end

  def log_blocking_action(block)
    Rails.logger.info "User #{@user.id} blocked: #{block.reason}"
    # Could add to audit log here
  end

  def log_unblocking_action(block)
    Rails.logger.info "User #{@user.id} unblocked"
    # Could add to audit log here
  end
end

