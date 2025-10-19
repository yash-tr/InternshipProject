class CreateResumeTemplates < ActiveRecord::Migration[7.0]
  def change
    create_table :resume_templates do |t|
      t.string :name, null: false
      t.string :slug, null: false
      t.text :description
      t.string :category, null: false
      t.boolean :is_premium, default: false
      t.json :template_config, default: {}
      t.json :sections, default: []
      t.string :preview_image_url
      t.boolean :is_active, default: true
      t.integer :usage_count, default: 0
      t.decimal :generation_time_avg, precision: 8, scale: 2
      t.timestamps
    end

    add_index :resume_templates, :slug, unique: true
    add_index :resume_templates, :category
    add_index :resume_templates, :is_premium
    add_index :resume_templates, :is_active
  end
end
