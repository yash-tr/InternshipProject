class CreateAnalyticsEvents < ActiveRecord::Migration[7.0]
  def change
    create_table :analytics_events do |t|
      t.references :user, null: true, foreign_key: true
      t.string :event_name, null: false
      t.string :event_category, null: false
      t.json :properties, default: {}
      t.string :session_id
      t.string :ip_address
      t.string :user_agent
      t.string :referrer
      t.string :page_url
      t.datetime :occurred_at, null: false
      t.timestamps
    end

    add_index :analytics_events, :user_id
    add_index :analytics_events, :event_name
    add_index :analytics_events, :event_category
    add_index :analytics_events, :occurred_at
    add_index :analytics_events, :session_id
  end
end
