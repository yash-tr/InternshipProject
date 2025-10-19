class HomeController < ApplicationController
  def index
    render json: {
      message: 'Resume Builder Platform API',
      version: '1.0.0',
      status: 'operational',
      documentation: '/api/docs',
      health_check: '/health'
    }
  end
end
