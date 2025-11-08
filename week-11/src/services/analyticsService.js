// Analytics Service for Mixpanel Integration
// Handles all event tracking for the application

class AnalyticsService {
  constructor() {
    this.mixpanelToken = process.env.REACT_APP_MIXPANEL_TOKEN;
    this.enabled = !!this.mixpanelToken && process.env.NODE_ENV === 'production';
    
    if (this.enabled && window.mixpanel) {
      window.mixpanel.init(this.mixpanelToken);
    }
  }

  // Track generic event
  trackEvent(eventName, properties = {}) {
    if (!this.enabled || !window.mixpanel) {
      console.log('Analytics event:', eventName, properties);
      return;
    }

    try {
      const eventProperties = {
        ...properties,
        timestamp: new Date().toISOString(),
        environment: process.env.NODE_ENV
      };

      window.mixpanel.track(eventName, eventProperties);
    } catch (error) {
      console.error('Error tracking event:', error);
    }
  }

  // Track page view
  trackPageView(pageName, properties = {}) {
    this.trackEvent('page_view', {
      ...properties,
      page_name: page_name
    });
  }

  // Track button click
  trackButtonClick(buttonName, properties = {}) {
    this.trackEvent('button_click', {
      ...properties,
      button_name: buttonName
    });
  }

  // Track modal interaction
  trackModalInteraction(user, modalName, action, properties = {}) {
    this.trackEvent('modal_interaction', {
      ...properties,
      modal_name: modalName,
      action: action,
      user_id: user?.id,
      user_type: user?.user_type
    });
  }

  // Track flagging action
  trackFlagging(user, flagType, properties = {}) {
    this.trackEvent('flagging_action', {
      ...properties,
      flag_type: flagType,
      user_id: user?.id,
      user_type: user?.user_type
    });
  }

  // Track policy acknowledgment
  trackPolicyAcknowledgment(user, policyId, properties = {}) {
    this.trackEvent('policy_acknowledged', {
      ...properties,
      policy_id: policyId,
      user_id: user?.id,
      user_type: user?.user_type
    });
  }

  // Track save button interaction
  trackSaveButton(user, action, entityType, entityId, properties = {}) {
    this.trackEvent('save_button_interaction', {
      ...properties,
      action: action, // 'saved' or 'unsaved'
      entity_type: entityType,
      entity_id: entityId,
      user_id: user?.id,
      user_type: user?.user_type
    });
  }

  // Identify user
  identify(user) {
    if (!this.enabled || !window.mixpanel) return;

    try {
      window.mixpanel.identify(user.id.toString());
      window.mixpanel.people.set({
        '$email': user.email,
        '$name': user.full_name,
        'user_type': user.user_type,
        'created_at': user.created_at
      });
    } catch (error) {
      console.error('Error identifying user:', error);
    }
  }

  // Set user properties
  setUserProperties(properties) {
    if (!this.enabled || !window.mixpanel) return;

    try {
      window.mixpanel.people.set(properties);
    } catch (error) {
      console.error('Error setting user properties:', error);
    }
  }
}

// Export singleton instance
export default new AnalyticsService();

// Export individual functions for convenience
export const trackEvent = (eventName, properties) => {
  analyticsService.trackEvent(eventName, properties);
};

export const trackPageView = (pageName, properties) => {
  analyticsService.trackPageView(pageName, properties);
};

export const trackButtonClick = (buttonName, properties) => {
  analyticsService.trackButtonClick(buttonName, properties);
};

export const trackModalInteraction = (user, modalName, action, properties) => {
  analyticsService.trackModalInteraction(user, modalName, action, properties);
};

export const trackFlagging = (user, flagType, properties) => {
  analyticsService.trackFlagging(user, flagType, properties);
};

export const trackPolicyAcknowledgment = (user, policyId, properties) => {
  analyticsService.trackPolicyAcknowledgment(user, policyId, properties);
};

export const trackSaveButton = (user, action, entityType, entityId, properties) => {
  analyticsService.trackSaveButton(user, action, entityType, entityId, properties);
};

export const identifyUser = (user) => {
  analyticsService.identify(user);
};

