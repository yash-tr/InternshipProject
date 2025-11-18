#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative "../config/environment"

unless ARGV[0]
  puts "Usage: ruby scripts/manual_highlight_runner.rb BATCH_SIZE"
  exit 1
end

batch_size = ARGV[0].to_i
raise "Batch size must be positive" if batch_size <= 0

puts "Starting manual highlight backfill with batch size=#{batch_size}"
JobHighlightService.new.backfill!(batch_size: batch_size)
puts "Backfill complete"

