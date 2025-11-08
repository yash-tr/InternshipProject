# Auto Blocking Job
# Processes critical flags and auto-blocks users if necessary

class AutoBlockingJob < ApplicationJob
  queue_as :default

  def perform(flag_id)
    flag = Flag.find(flag_id)

    return unless flag.severity == 'critical'
    return if flag.flagged_entity_type != 'User'

    user = flag.flagged_entity
    blocker = UserBlockerService.new(user)

    # Auto-block user for critical violations
    result = blocker.block(
      reason: "Auto-blocked due to critical flag: #{flag.violation_type}",
      duration: 30, # 30 days
      block_type: 'full',
      flag_id: flag.id
    )

    if result[:success]
      Rails.logger.info "Auto-blocked user #{user.id} due to critical flag #{flag.id}"
      
      # Notify admins
      AdminNotificationService.new.notify_auto_block(user, flag)
    else
      Rails.logger.error "Failed to auto-block user #{user.id}: #{result[:error]}"
    end
  rescue => e
    Rails.logger.error "Error in AutoBlockingJob: #{e.message}"
    raise
  end
end

