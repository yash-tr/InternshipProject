# Admin Notification Service
# Handles notifications to admin users

class AdminNotificationService
  def notify_flag_created(flag)
    return unless flag.severity == 'high' || flag.severity == 'critical'

    admins = User.where(role: 'admin', notifications_enabled: true)
    
    admins.each do |admin|
      # Send email notification
      AdminMailer.flag_created_notification(admin, flag).deliver_later
      
      # Send in-app notification
      Notification.create!(
        user: admin,
        title: "New #{flag.severity} flag",
        message: "A #{flag.severity} flag has been created for #{flag.flagged_entity_type}",
        notification_type: 'flag',
        metadata: { flag_id: flag.id }
      )
    end
  end

  def notify_critical_flag(flag)
    admins = User.where(role: 'admin', notifications_enabled: true)
    
    admins.each do |admin|
      # Send urgent notification
      AdminMailer.critical_flag_notification(admin, flag).deliver_now
      
      # Send in-app notification with high priority
      Notification.create!(
        user: admin,
        title: "URGENT: Critical Flag",
        message: "A critical flag requires immediate attention",
        notification_type: 'critical_flag',
        priority: 'high',
        metadata: { flag_id: flag.id }
      )
    end
  end

  def notify_misconduct_report(report)
    admins = User.where(role: 'admin', notifications_enabled: true)
    
    admins.each do |admin|
      AdminMailer.misconduct_report_notification(admin, report).deliver_later
    end
  end

  def notify_auto_block(user, flag)
    admins = User.where(role: 'admin', notifications_enabled: true)
    
    admins.each do |admin|
      AdminMailer.auto_block_notification(admin, user, flag).deliver_later
    end
  end
end

