class Api::V1::AuthenticationController < ApplicationController
  before_action :authenticate_user!, only: [:me, :logout]

  def login
    user = User.find_by(email: login_params[:email])
    
    if user&.valid_password?(login_params[:password])
      if user.confirmed?
        sign_in(user)
        
        # Track login event
        user.track_event('user_login', {
          ip_address: request.remote_ip,
          user_agent: request.user_agent
        })
        
        render json: {
          success: true,
          user: user_serializer(user),
          token: generate_jwt_token(user)
        }
      else
        render json: {
          success: false,
          error: 'Please confirm your email address before logging in'
        }, status: :unprocessable_entity
      end
    else
      render json: {
        success: false,
        error: 'Invalid email or password'
      }, status: :unauthorized
    end
  end

  def logout
    # Track logout event
    current_user.track_event('user_logout', {
      ip_address: request.remote_ip,
      user_agent: request.user_agent
    })
    
    sign_out(current_user)
    
    render json: {
      success: true,
      message: 'Successfully logged out'
    }
  end

  def me
    render json: {
      success: true,
      user: user_serializer(current_user)
    }
  end

  private

  def login_params
    params.require(:user).permit(:email, :password)
  end

  def user_serializer(user)
    {
      id: user.id,
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      full_name: user.full_name,
      is_premium: user.premium?,
      subscription_tier: user.subscription_tier,
      subscription_expires_at: user.subscription_expires_at,
      preferences: user.preferences,
      created_at: user.created_at,
      updated_at: user.updated_at
    }
  end

  def generate_jwt_token(user)
    # In a real application, you'd use JWT gem
    # For now, we'll use a simple token
    "token_#{user.id}_#{SecureRandom.hex(16)}"
  end
end
