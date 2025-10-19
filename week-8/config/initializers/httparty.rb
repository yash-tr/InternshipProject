require 'httparty'

# Configure HTTParty for external API calls
HTTParty::Options.default_timeout = 30
HTTParty::Options.default_headers = {
  'User-Agent' => 'ResumeBuilderPlatform/1.0',
  'Accept' => 'application/json',
  'Content-Type' => 'application/json'
}
