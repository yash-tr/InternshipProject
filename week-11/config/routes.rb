# Additional routes for Week 11 features

Rails.application.routes.draw do
  namespace :api do
    namespace :v1 do
      # Flagging routes
      resources :flagging, only: [:index, :show, :create, :update] do
        member do
          patch :resolve
        end
        collection do
          get :statistics
        end
      end

      # Policy misconduct routes
      resource :policy_misconduct, only: [:show] do
        post :acknowledge
        post :report
        get :check_acknowledgment
        get :acknowledgment_history
      end

      # User blocker routes
      resource :user_blocker, only: [:index] do
        get ':user_id/check', to: 'user_blocker#check', as: 'check'
        post ':user_id/block', to: 'user_blocker#block', as: 'block'
        post ':user_id/unblock', to: 'user_blocker#unblock', as: 'unblock'
        get ':user_id/history', to: 'user_blocker#history', as: 'history'
      end

      # Jobs routes (extended)
      resources :jobs, only: [:index, :show] do
        member do
          post :save
          delete :unsave
        end
        collection do
          get :saved
        end
      end
    end
  end
end

