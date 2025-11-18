require "rails_helper"

RSpec.describe JobHighlightService do
  let(:repository) { class_double(JobHighlightRepository).as_stubbed_const }
  let(:service) { described_class.new(repository: repository) }

  describe "#create_highlight!" do
    it "persists highlight and records analytics" do
      expect(repository).to receive(:create!).with(job_id: 7, summary: "Great role", tags: %w[ruby remote]).and_return(double(as_json: {}))

      service.create_highlight!(job_id: 7, summary: "Great role", tags: %w[ruby remote])
    end
  end
end

