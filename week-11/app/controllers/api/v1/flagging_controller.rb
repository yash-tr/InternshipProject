# Flagging Controller for Recruiter Portal
# Handles flagging of job postings and users for policy violations

class Api::V1::FlaggingController < ApplicationController
  before_action :authenticate_user!
  before_action :authorize_recruiter!, except: [:index, :show]
  before_action :set_flag, only: [:show, :update, :resolve]

  # List all flags (with filtering)
  def index
    @flags = Flag.includes(:flagged_by, :flagged_entity)
                 .order(created_at: :desc)
                 .page(params[:page])
                 .per(params[:per_page] || 20)

    # Filter by status
    @flags = @flags.where(status: params[:status]) if params[:status].present?

    # Filter by severity
    @flags = @flags.where(severity: params[:severity]) if params[:severity].present?

    # Filter by entity type
    @flags = @flags.where(flagged_entity_type: params[:entity_type]) if params[:entity_type].present?

    render json: {
      success: true,
      flags: @flags.map { |flag| flag_serializer(flag) },
      pagination: {
        current_page: @flags.current_page,
        total_pages: @flags.total_pages,
        total_count: @flags.total_count,
        per_page: @flags.limit_value
      }
    }
  end

  # Show specific flag
  def show
    render json: {
      success: true,
      flag: flag_serializer(@flag)
    }
  end

  # Create a new flag
  def create
    @flag = Flag.new(flag_params)
    @flag.flagged_by = current_user
    @flag.status = 'pending'

    # Validate flagged entity exists
    entity = find_flagged_entity
    unless entity
      return render json: {
        success: false,
        error: 'Flagged entity not found'
      }, status: :not_found
    end

    @flag.flagged_entity = entity

    # Check for duplicate flags
    if duplicate_flag_exists?
      return render json: {
        success: false,
        error: 'This entity has already been flagged by you'
      }, status: :conflict
    end

    if @flag.save
      # Track analytics event
      track_flagging_event('flag_created', @flag)

      # Send notification to admins for high severity
      notify_admins if @flag.severity == 'high'

      # Process auto-blocking for severe violations
      process_auto_blocking if @flag.severity == 'critical'

      render json: {
        success: true,
        flag: flag_serializer(@flag),
        message: 'Flag submitted successfully'
      }, status: :created
    else
      render json: {
        success: false,
        errors: @flag.errors.full_messages
      }, status: :unprocessable_entity
    end
  end

  # Update flag status (admin only)
  def update
    authorize @flag, :update?

    if @flag.update(flag_update_params)
      # Track status change
      track_flagging_event('flag_updated', @flag)

      # Handle resolution actions
      if @flag.status == 'resolved'
        handle_flag_resolution
      end

      render json: {
        success: true,
        flag: flag_serializer(@flag)
      }
    else
      render json: {
        success: false,
        errors: @flag.errors.full_messages
      }, status: :unprocessable_entity
    end
  end

  # Resolve flag (admin only)
  def resolve
    authorize @flag, :resolve?

    @flag.update!(
      status: 'resolved',
      resolved_by: current_user,
      resolved_at: Time.current,
      resolution_notes: params[:resolution_notes]
    )

    handle_flag_resolution

    track_flagging_event('flag_resolved', @flag)

    render json: {
      success: true,
      flag: flag_serializer(@flag),
      message: 'Flag resolved successfully'
    }
  end

  # Get flag statistics
  def statistics
    stats = {
      total_flags: Flag.count,
      pending_flags: Flag.where(status: 'pending').count,
      resolved_flags: Flag.where(status: 'resolved').count,
      rejected_flags: Flag.where(status: 'rejected').count,
      by_severity: Flag.group(:severity).count,
      by_entity_type: Flag.group(:flagged_entity_type).count,
      by_violation_type: Flag.group(:violation_type).count
    }

    render json: {
      success: true,
      statistics: stats
    }
  end

  private

  def set_flag
    @flag = Flag.find(params[:id])
  end

  def flag_params
    params.require(:flag).permit(
      :flagged_entity_type,
      :flagged_entity_id,
      :violation_type,
      :severity,
      :reason,
      :details,
      :evidence_urls
    )
  end

  def flag_update_params
    params.require(:flag).permit(
      :status,
      :severity,
      :resolution_notes
    )
  end

  def find_flagged_entity
    entity_type = params[:flag][:flagged_entity_type]
    entity_id = params[:flag][:flagged_entity_id]

    case entity_type
    when 'JobPosting'
      JobPosting.find_by(id: entity_id)
    when 'User'
      User.find_by(id: entity_id)
    when 'Resume'
      Resume.find_by(id: entity_id)
    else
      nil
    end
  end

  def duplicate_flag_exists?
    Flag.exists?(
      flagged_by: current_user,
      flagged_entity_type: @flag.flagged_entity_type,
      flagged_entity_id: @flag.flagged_entity_id,
      status: ['pending', 'resolved']
    )
  end

  def authorize_recruiter!
    unless current_user.recruiter? || current_user.admin?
      render json: {
        success: false,
        error: 'Unauthorized. Recruiter or admin access required.'
      }, status: :forbidden
    end
  end

  def notify_admins
    AdminNotificationService.new.notify_flag_created(@flag)
  end

  def process_auto_blocking
    AutoBlockingService.new.process_critical_flag(@flag)
  end

  def handle_flag_resolution
    case @flag.flagged_entity_type
    when 'JobPosting'
      handle_job_posting_resolution
    when 'User'
      handle_user_resolution
    end
  end

  def handle_job_posting_resolution
    job = @flag.flagged_entity
    if @flag.resolution_notes&.include?('remove_job')
      job.update!(status: 'removed', removed_reason: @flag.resolution_notes)
    end
  end

  def handle_user_resolution
    user = @flag.flagged_entity
    if @flag.resolution_notes&.include?('block_user')
      UserBlockingService.new.block_user(user, @flag.reason)
    end
  end

  def track_flagging_event(event_name, flag)
    AnalyticsService.track_event(current_user, event_name, {
      flag_id: flag.id,
      violation_type: flag.violation_type,
      severity: flag.severity,
      entity_type: flag.flagged_entity_type,
      entity_id: flag.flagged_entity_id
    })
  end

  def flag_serializer(flag)
    {
      id: flag.id,
      flagged_entity_type: flag.flagged_entity_type,
      flagged_entity_id: flag.flagged_entity_id,
      flagged_entity: flag.flagged_entity.as_json(only: [:id, :title, :name, :email]),
      violation_type: flag.violation_type,
      severity: flag.severity,
      reason: flag.reason,
      details: flag.details,
      evidence_urls: flag.evidence_urls,
      status: flag.status,
      flagged_by: {
        id: flag.flagged_by.id,
        name: flag.flagged_by.full_name,
        email: flag.flagged_by.email
      },
      resolved_by: flag.resolved_by ? {
        id: flag.resolved_by.id,
        name: flag.resolved_by.full_name
      } : nil,
      resolved_at: flag.resolved_at,
      resolution_notes: flag.resolution_notes,
      created_at: flag.created_at,
      updated_at: flag.updated_at
    }
  end
end

