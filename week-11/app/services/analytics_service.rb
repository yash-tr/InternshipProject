# Analytics Service
# Handles Mixpanel event tracking

class AnalyticsService
  class << self
    # Track event to Mixpanel
    def track_event(user, event_name, properties = {})
      return unless mixpanel_enabled?

      begin
        tracker = Mixpanel::Tracker.new(ENV['MIXPANEL_TOKEN'])

        # Add user properties
        user_properties = {
          user_id: user.id,
          email: user.email,
          user_type: user.user_type,
          created_at: user.created_at
        }

        # Merge with custom properties
        event_properties = user_properties.merge(properties).merge(
          timestamp: Time.current.to_i,
          environment: Rails.env
        )

        # Track event
        tracker.track(user.id.to_s, event_name, event_properties)

        # Update user profile
        tracker.people.set(user.id.to_s, user_properties)

        Rails.logger.info "Analytics event tracked: #{event_name} for user #{user.id}"
      rescue => e
        Rails.logger.error "Error tracking analytics event: #{e.message}"
        # Don't raise error, analytics failures shouldn't break the app
      end
    end

    # Track page view
    def track_page_view(user, page_name, properties = {})
      track_event(user, 'page_view', properties.merge(page_name: page_name))
    end

    # Track button click
    def track_button_click(user, button_name, properties = {})
      track_event(user, 'button_click', properties.merge(button_name: button_name))
    end

    # Track modal interaction
    def track_modal_interaction(user, modal_name, action, properties = {})
      track_event(user, 'modal_interaction', properties.merge(
        modal_name: modal_name,
        action: action
      ))
    end

    # Track flagging action
    def track_flagging(user, flag_type, properties = {})
      track_event(user, 'flagging_action', properties.merge(flag_type: flag_type))
    end

    # Track policy acknowledgment
    def track_policy_acknowledgment(user, policy_id, properties = {})
      track_event(user, 'policy_acknowledged', properties.merge(policy_id: policy_id))
    end

    # Track save button interaction
    def track_save_button(user, action, entity_type, entity_id, properties = {})
      track_event(user, 'save_button_interaction', properties.merge(
        action: action, # 'saved' or 'unsaved'
        entity_type: entity_type,
        entity_id: entity_id
      ))
    end

    private

    def mixpanel_enabled?
      ENV['MIXPANEL_TOKEN'].present? && Rails.env.production?
    end
  end
end

