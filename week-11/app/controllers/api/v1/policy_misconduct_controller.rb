# Policy Misconduct Controller
# Handles policy violations, misconduct modals, and user acknowledgments

class Api::V1::PolicyMisconductController < ApplicationController
  before_action :authenticate_user!

  # Get current policy content
  def show
    policy = PolicyMisconduct.current_policy

    render json: {
      success: true,
      policy: {
        id: policy.id,
        version: policy.version,
        title: policy.title,
        content: policy.content,
        last_updated: policy.updated_at,
        requires_acknowledgment: policy.requires_acknowledgment,
        severity_level: policy.severity_level
      },
      user_acknowledged: current_user.policy_acknowledgments.exists?(policy_id: policy.id)
    }
  end

  # Acknowledge policy
  def acknowledge
    policy = PolicyMisconduct.find(params[:policy_id])

    acknowledgment = current_user.policy_acknowledgments.find_or_initialize_by(
      policy_id: policy.id
    )

    acknowledgment.acknowledged_at = Time.current
    acknowledgment.ip_address = request.remote_ip
    acknowledgment.user_agent = request.user_agent

    if acknowledgment.save
      # Track analytics event
      track_policy_event('policy_acknowledged', policy)

      render json: {
        success: true,
        message: 'Policy acknowledged successfully',
        acknowledgment: {
          id: acknowledgment.id,
          policy_id: policy.id,
          acknowledged_at: acknowledgment.acknowledged_at
        }
      }
    else
      render json: {
        success: false,
        errors: acknowledgment.errors.full_messages
      }, status: :unprocessable_entity
    end
  end

  # Report misconduct
  def report
    report = PolicyMisconductReport.new(report_params)
    report.reported_by = current_user
    report.status = 'pending'

    if report.save
      # Track analytics event
      track_policy_event('misconduct_reported', report)

      # Notify admins
      notify_admins(report)

      render json: {
        success: true,
        message: 'Misconduct report submitted successfully',
        report: {
          id: report.id,
          status: report.status,
          reported_at: report.created_at
        }
      }, status: :created
    else
      render json: {
        success: false,
        errors: report.errors.full_messages
      }, status: :unprocessable_entity
    end
  end

  # Check if user needs to see policy modal
  def check_acknowledgment
    policy = PolicyMisconduct.current_policy
    requires_acknowledgment = policy.requires_acknowledgment && 
                              !current_user.policy_acknowledgments.exists?(policy_id: policy.id)

    # Check for recent policy updates
    last_acknowledgment = current_user.policy_acknowledgments
                                      .where(policy_id: policy.id)
                                      .order(acknowledged_at: :desc)
                                      .first

    if last_acknowledgment && policy.updated_at > last_acknowledgment.acknowledged_at
      requires_acknowledgment = true
    end

    render json: {
      success: true,
      requires_acknowledgment: requires_acknowledgment,
      policy_version: policy.version,
      last_acknowledged_version: last_acknowledgment&.policy_version
    }
  end

  # Get user's acknowledgment history
  def acknowledgment_history
    acknowledgments = current_user.policy_acknowledgments
                                  .includes(:policy)
                                  .order(acknowledged_at: :desc)
                                  .page(params[:page])
                                  .per(params[:per_page] || 10)

    render json: {
      success: true,
      acknowledgments: acknowledgments.map { |ack| acknowledgment_serializer(ack) },
      pagination: {
        current_page: acknowledgments.current_page,
        total_pages: acknowledgments.total_pages,
        total_count: acknowledgments.total_count
      }
    }
  end

  private

  def report_params
    params.require(:report).permit(
      :policy_id,
      :violation_type,
      :description,
      :reported_entity_type,
      :reported_entity_id,
      :evidence_urls
    )
  end

  def track_policy_event(event_name, entity)
    AnalyticsService.track_event(current_user, event_name, {
      policy_id: entity.is_a?(PolicyMisconduct) ? entity.id : entity.policy_id,
      policy_version: entity.is_a?(PolicyMisconduct) ? entity.version : entity.policy.version,
      violation_type: entity.respond_to?(:violation_type) ? entity.violation_type : nil
    })
  end

  def notify_admins(report)
    AdminNotificationService.new.notify_misconduct_report(report)
  end

  def acknowledgment_serializer(acknowledgment)
    {
      id: acknowledgment.id,
      policy: {
        id: acknowledgment.policy.id,
        version: acknowledgment.policy.version,
        title: acknowledgment.policy.title
      },
      acknowledged_at: acknowledgment.acknowledged_at,
      ip_address: acknowledgment.ip_address
    }
  end
end

