class CreateUserBlocks < ActiveRecord::Migration[7.0]
  def change
    create_table :user_blocks do |t|
      t.references :user, null: false, foreign_key: true
      t.references :blocked_by, null: false, foreign_key: { to_table: :users }
      t.references :unblocked_by, null: true, foreign_key: { to_table: :users }
      t.references :flag, null: true, foreign_key: true
      
      t.string :block_type, null: false
      t.text :reason, null: false
      t.string :status, null: false, default: 'active'
      t.integer :duration_days
      t.datetime :expires_at
      t.datetime :unblocked_at
      t.text :unblock_reason
      
      t.timestamps
    end

    add_index :user_blocks, :status
    add_index :user_blocks, :block_type
    add_index :user_blocks, :user_id
    add_index :user_blocks, :expires_at
  end
end

