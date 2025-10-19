class CreateResumes < ActiveRecord::Migration[7.0]
  def change
    create_table :resumes do |t|
      t.references :user, null: false, foreign_key: true
      t.string :title, null: false
      t.text :content, null: false
      t.string :template_name, null: false
      t.string :status, default: 'draft'
      t.json :metadata, default: {}
      t.json :personal_info, default: {}
      t.json :experience, default: []
      t.json :education, default: []
      t.json :skills, default: []
      t.json :projects, default: []
      t.string :file_path
      t.string :file_format, default: 'pdf'
      t.integer :generation_time_ms
      t.integer :api_calls_count, default: 0
      t.boolean :is_optimized, default: false
      t.datetime :generated_at
      t.timestamps
    end

    add_index :resumes, :user_id
    add_index :resumes, :status
    add_index :resumes, :template_name
    add_index :resumes, :is_optimized
    add_index :resumes, :generated_at
  end
end
