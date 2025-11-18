class CreateJobHighlights < ActiveRecord::Migration[7.0]
  def change
    create_table :job_highlights do |t|
      t.bigint :job_id, null: false
      t.text :summary, null: false
      t.jsonb :tags, null: false, default: []
      t.float :score, null: false, default: 0.0

      t.timestamps
    end

    add_index :job_highlights, :job_id, unique: true
    add_index :job_highlights, :score
  end
end

