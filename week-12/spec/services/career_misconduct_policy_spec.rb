require "rails_helper"

RSpec.describe CareerMisconductPolicy do
  describe "#block_user!" do
    it "creates block and enqueues enforcement worker" do
      policy = described_class.new
      allow(PolicyEnforcementWorker).to receive(:perform_async)

      expect { policy.block_user!(reviewer_id: 1, target_id: 2, reason: "spam") }
        .to change { UserBlock.count }.by(1)

      expect(PolicyEnforcementWorker).to have_received(:perform_async).with(2)
    end
  end
end

