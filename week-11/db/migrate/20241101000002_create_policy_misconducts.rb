class CreatePolicyMisconducts < ActiveRecord::Migration[7.0]
  def change
    create_table :policy_misconducts do |t|
      t.string :version, null: false
      t.string :title, null: false
      t.text :content, null: false
      t.string :severity_level, null: false, default: 'info'
      t.boolean :requires_acknowledgment, default: false
      t.boolean :is_active, default: true
      
      t.timestamps
    end

    add_index :policy_misconducts, :version, unique: true
    add_index :policy_misconducts, :is_active
  end
end

