require "rails_helper"

RSpec.describe JobTagsRolloutService do
  describe "#rollout_to_all_users!" do
    it "removes flag and migrates users" do
      FeatureFlag.create!(key: described_class::FLAG_KEY, enabled: true)
      create_list(:user, 2, job_tags_state: nil)

      result = described_class.new.rollout_to_all_users!

      expect(result[:migrated_users]).to eq(2)
      expect(FeatureFlag.enabled?(described_class::FLAG_KEY)).to be_falsey
    end
  end
end

