# API Integration Tests
require 'rails_helper'

RSpec.describe 'API Integration', type: :request do
  let(:user) { create(:user, :confirmed) }
  let(:token) { 'test_token' } # In production, generate actual JWT

  describe 'Authentication Flow' do
    it 'allows user to login' do
      post '/api/v1/auth/login', params: {
        email: user.email,
        password: 'password123'
      }

      expect(response).to have_http_status(:ok)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be true
      expect(json_response['data']).to have_key('user')
      expect(json_response['data']).to have_key('token')
    end

    it 'rejects invalid credentials' do
      post '/api/v1/auth/login', params: {
        email: user.email,
        password: 'wrong_password'
      }

      expect(response).to have_http_status(:unauthorized)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be false
    end

    it 'returns current user with valid token' do
      get '/api/v1/auth/me', headers: {
        'Authorization' => "Bearer #{token}"
      }

      expect(response).to have_http_status(:ok)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be true
    end
  end

  describe 'Resume Management' do
    let(:premium_user) { create(:user, :premium, :confirmed) }

    before do
      # Setup authentication
      allow_any_instance_of(ApiAuthMiddleware).to receive(:current_user_from_token)
        .and_return(user)
    end

    it 'creates a new resume' do
      post '/api/v1/resumes', params: {
        resume: {
          title: 'My Resume',
          template_name: 'modern_professional',
          personal_info: { phone: '123-456-7890' }
        }
      }, headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:created)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be true
      expect(json_response['resume']).to have_key('id')
      expect(json_response['resume']['title']).to eq('My Resume')
    end

    it 'lists user resumes' do
      create_list(:resume, 3, user: user)

      get '/api/v1/resumes', headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:ok)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be true
      expect(json_response['resumes'].count).to eq(3)
    end

    it 'prevents quota exceeded users from creating resumes' do
      # Create 3 resumes (quota limit)
      create_list(:resume, 3, user: user)

      post '/api/v1/resumes', params: {
        resume: { title: 'Fourth Resume', template_name: 'modern_professional' }
      }, headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:forbidden)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be false
      expect(json_response['error']).to include('quota')
    end

    it 'allows premium users unlimited resumes' do
      allow_any_instance_of(ApiAuthMiddleware).to receive(:current_user_from_token)
        .and_return(premium_user)

      create_list(:resume, 10, user: premium_user)

      post '/api/v1/resumes', params: {
        resume: { title: 'Eleventh Resume', template_name: 'modern_professional' }
      }, headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:created)
    end
  end

  describe 'PDF Generation' do
    let(:resume) { create(:resume, user: user) }

    before do
      allow_any_instance_of(ApiAuthMiddleware).to receive(:current_user_from_token)
        .and_return(user)
    end

    it 'starts PDF generation job' do
      post "/api/v1/resumes/#{resume.id}/generate_pdf",
           headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:ok)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be true
      expect(json_response['status']).to eq('generating')
    end

    it 'prevents concurrent PDF generation' do
      resume.update!(status: 'generating')

      post "/api/v1/resumes/#{resume.id}/generate_pdf",
           headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:conflict)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be false
    end
  end

  describe 'Templates' do
    before do
      create(:resume_template, name: 'Modern Professional')
      create(:resume_template, :premium, name: 'Premium Template')
      create(:resume_template, :creative, name: 'Creative Template')
    end

    it 'lists all templates' do
      get '/api/v1/templates'

      expect(response).to have_http_status(:ok)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be true
      expect(json_response['templates'].count).to eq(3)
    end

    it 'shows only free templates to non-authenticated users' do
      get '/api/v1/templates'

      json_response = JSON.parse(response.body)
      templates = json_response['templates']
      expect(templates.none? { |t| t['is_premium'] }).to be true
    end

    it 'shows premium templates to authenticated premium users' do
      premium_user = create(:user, :premium)
      allow_any_instance_of(ApiAuthMiddleware).to receive(:current_user_from_token)
        .and_return(premium_user)

      get '/api/v1/templates', headers: { 'Authorization' => "Bearer #{token}" }

      json_response = JSON.parse(response.body)
      templates = json_response['templates']
      expect(templates.any? { |t| t['is_premium'] }).to be true
    end
  end

  describe 'Analytics' do
    before do
      allow_any_instance_of(ApiAuthMiddleware).to receive(:current_user_from_token)
        .and_return(user)
      create_list(:resume, 5, user: user, :completed)
    end

    it 'returns dashboard analytics' do
      get '/api/v1/analytics/dashboard', headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:ok)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be true
      expect(json_response['analytics']).to have_key('total_resumes')
      expect(json_response['analytics']).to have_key('completed_resumes')
    end

    it 'returns user-specific analytics' do
      get '/api/v1/resumes/analytics', headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:ok)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be true
      expect(json_response['analytics']['total_resumes']).to eq(5)
    end
  end

  describe 'Error Handling' do
    it 'returns 404 for non-existent resources' do
      get '/api/v1/resumes/99999', headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:not_found)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be false
    end

    it 'returns 401 for invalid token' do
      get '/api/v1/resumes', headers: { 'Authorization' => 'Bearer invalid_token' }

      expect(response).to have_http_status(:unauthorized)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be false
      expect(json_response['error']).to eq('Unauthorized')
    end

    it 'returns validation errors for invalid data' do
      post '/api/v1/resumes', params: {
        resume: { title: '' } # Invalid: empty title
      }, headers: { 'Authorization' => "Bearer #{token}" }

      expect(response).to have_http_status(:unprocessable_entity)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be false
      expect(json_response['errors']).to be_present
    end
  end

  describe 'Rate Limiting' do
    it 'limits requests per minute' do
      # Make 101 requests (assuming default limit is 100)
      101.times do
        get '/api/v1/templates'
      end

      expect(response).to have_http_status(:too_many_requests)
      json_response = JSON.parse(response.body)
      expect(json_response['success']).to be false
      expect(json_response['error']).to eq('Rate Limit Exceeded')
    end
  end
end

