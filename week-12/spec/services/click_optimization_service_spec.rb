require "rails_helper"

RSpec.describe ClickOptimizationService do
  let(:rank_client) { instance_double(ClickOptimizationRanker, rank: %w[2 1]) }
  let(:metrics) { instance_double(AnalyticsService, track: true) }
  subject(:service) { described_class.new(rank_client: rank_client, metrics: metrics) }

  it "returns ranked ids with token" do
    result = service.rank!(user_id: 5, job_ids: %w[1 2], context: "search")
    expect(result[:job_ids]).to eq(%w[2 1])
    expect(result[:impression_token]).to be_present
    expect(metrics).to have_received(:track)
  end
end

