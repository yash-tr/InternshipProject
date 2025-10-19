class CreateJobExecutions < ActiveRecord::Migration[7.0]
  def change
    create_table :job_executions do |t|
      t.string :job_name, null: false
      t.string :status, default: 'pending'
      t.text :error_message
      t.json :parameters, default: {}
      t.json :result, default: {}
      t.datetime :started_at
      t.datetime :completed_at
      t.integer :execution_time_ms
      t.string :worker_id
      t.string :queue_name
      t.integer :retry_count, default: 0
      t.boolean :success, default: false
      t.timestamps
    end

    add_index :job_executions, :job_name
    add_index :job_executions, :status
    add_index :job_executions, :started_at
    add_index :job_executions, :success
    add_index :job_executions, :queue_name
  end
end
