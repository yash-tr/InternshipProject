class CreateFlags < ActiveRecord::Migration[7.0]
  def change
    create_table :flags do |t|
      t.references :flagged_by, null: false, foreign_key: { to_table: :users }
      t.references :flagged_entity, polymorphic: true, null: false
      t.references :resolved_by, null: true, foreign_key: { to_table: :users }
      
      t.string :violation_type, null: false
      t.string :severity, null: false, default: 'medium'
      t.string :status, null: false, default: 'pending'
      t.text :reason, null: false
      t.text :details
      t.json :evidence_urls
      t.text :resolution_notes
      
      t.datetime :resolved_at
      
      t.timestamps
    end

    add_index :flags, :status
    add_index :flags, :severity
    add_index :flags, :violation_type
    add_index :flags, [:flagged_entity_type, :flagged_entity_id]
    add_index :flags, :created_at
  end
end

