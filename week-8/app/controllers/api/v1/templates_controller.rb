class Api::V1::TemplatesController < ApplicationController
  before_action :authenticate_user!, except: [:index, :show, :popular, :fastest, :by_category]

  def index
    @templates = ResumeTemplate.active.includes(:resumes)
    
    # Apply filters
    @templates = @templates.by_category(params[:category]) if params[:category].present?
    @templates = @templates.premium if params[:premium_only] == 'true'
    @templates = @templates.free if params[:free_only] == 'true'
    
    # Apply search
    if params[:search].present?
      @templates = @templates.where(
        "name ILIKE ? OR description ILIKE ?", 
        "%#{params[:search]}%", 
        "%#{params[:search]}%"
      )
    end
    
    # Apply sorting
    case params[:sort]
    when 'popular'
      @templates = @templates.order(usage_count: :desc)
    when 'fastest'
      @templates = @templates.where.not(generation_time_avg: nil)
                            .order(:generation_time_avg)
    when 'newest'
      @templates = @templates.order(created_at: :desc)
    else
      @templates = @templates.order(:name)
    end
    
    # Pagination
    @templates = @templates.page(params[:page]).per(params[:per_page] || 20)
    
    render json: {
      success: true,
      templates: @templates.map { |template| template_serializer(template) },
      pagination: {
        current_page: @templates.current_page,
        total_pages: @templates.total_pages,
        total_count: @templates.total_count,
        per_page: @templates.limit_value
      }
    }
  end

  def show
    @template = ResumeTemplate.find_by(slug: params[:id])
    
    unless @template&.is_active?
      return render json: {
        success: false,
        error: 'Template not found'
      }, status: :not_found
    end
    
    # Check if user can access this template
    unless @template.available_for_user?(current_user)
      return render json: {
        success: false,
        error: 'Premium template requires premium subscription'
      }, status: :forbidden
    end
    
    render json: {
      success: true,
      template: template_serializer(@template)
    }
  end

  def popular
    # Use cached data for better performance
    templates = CachingService.cache_popular_templates
    
    render json: {
      success: true,
      templates: templates.map { |template| template_serializer(template) }
    }
  end

  def fastest
    @templates = ResumeTemplate.active
                              .where.not(generation_time_avg: nil)
                              .order(:generation_time_avg)
                              .limit(10)
    
    render json: {
      success: true,
      templates: @templates.map { |template| template_serializer(template) }
    }
  end

  def by_category
    category = params[:category]
    
    unless category.present?
      return render json: {
        success: false,
        error: 'Category parameter is required'
      }, status: :bad_request
    end
    
    @templates = ResumeTemplate.active.by_category(category)
    
    render json: {
      success: true,
      category: category,
      templates: @templates.map { |template| template_serializer(template) }
    }
  end

  private

  def template_serializer(template)
    {
      id: template.id,
      name: template.name,
      slug: template.slug,
      description: template.description,
      category: template.category,
      is_premium: template.is_premium,
      is_active: template.is_active,
      template_config: template.template_config,
      sections: template.sections_list,
      preview_image_url: template.preview_image_url,
      usage_count: template.usage_count,
      generation_time_avg: template.generation_time_avg,
      available_for_user: template.available_for_user?(current_user),
      created_at: template.created_at,
      updated_at: template.updated_at
    }
  end
end
