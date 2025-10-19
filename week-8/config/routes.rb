Rails.application.routes.draw do
  devise_for :users, controllers: {
    registrations: 'users/registrations',
    sessions: 'users/sessions'
  }

  # API routes
  namespace :api do
    namespace :v1 do
      # Authentication
      post 'auth/login', to: 'authentication#login'
      post 'auth/logout', to: 'authentication#logout'
      get 'auth/me', to: 'authentication#me'

      # User management
      resources :users, only: [:show, :update] do
        member do
          get :quota
          patch :upgrade_subscription
        end
      end

      # Resume templates
      resources :templates, only: [:index, :show] do
        collection do
          get :popular
          get :fastest
          get :by_category
        end
      end

      # Resume management
      resources :resumes do
        member do
          post :generate_pdf
          get :download
          post :optimize
          patch :regenerate
        end
        collection do
          get :analytics
          get :recent
        end
      end

      # Analytics and monitoring
      namespace :analytics do
        get :dashboard
        get :user_metrics
        get :system_health
        get :job_metrics
        get :conversion_funnel
      end

      # Admin endpoints
      namespace :admin do
        resources :job_executions, only: [:index, :show] do
          collection do
            get :success_rates
            get :performance_metrics
          end
        end
        
        resources :system_health, only: [:index] do
          collection do
            post :warm_cache
            post :clear_cache
            get :cache_status
          end
        end
      end
    end
  end

  # Health check endpoint
  get 'health', to: 'health#check'

  # Root path
  root 'home#index'
end
