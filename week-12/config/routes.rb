Rails.application.routes.draw do
  namespace :api do
    namespace :v1 do
      resources :job_tags, only: [:index, :update] do
        collection do
          post :rollout
        end
      end

      resources :click_optimizations, only: [:create]

      resources :career_misconducts, only: [:index, :create] do
        collection do
          post :block
          post :unblock
        end
      end

      resources :job_highlights, only: [:index, :create] do
        collection do
          post :backfill
        end
      end
    end
  end
end

