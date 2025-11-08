class AddBlockFieldsToUsers < ActiveRecord::Migration[7.0]
  def change
    add_column :users, :is_blocked, :boolean, default: false
    add_column :users, :blocked_reason, :text
    add_column :users, :job_portal_access, :boolean, default: true
    add_column :users, :notifications_enabled, :boolean, default: true
    
    add_index :users, :is_blocked
    add_index :users, :job_portal_access
  end
end

