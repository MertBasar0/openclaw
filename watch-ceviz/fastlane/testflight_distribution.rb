require "json"
require "spaceship"

config_path = File.expand_path("testflight-distribution.json", __dir__)
config = JSON.parse(File.read(config_path))
app_version = config.fetch("app_version")
build_number = config.fetch("build_number")
action = config.fetch("action", "audit")
requested_group = config["group"]&.strip

token = Spaceship::ConnectAPI::Token.create(
  key_id: ENV.fetch("ASC_KEY_ID"),
  issuer_id: ENV.fetch("ASC_ISSUER_ID"),
  filepath: File.expand_path(ENV.fetch("ASC_KEY_PATH"))
)
Spaceship::ConnectAPI.token = token

app = Spaceship::ConnectAPI::App.find("com.mertbasar.cevizwatch")
abort("Ceviz app not found in App Store Connect") unless app

build = Spaceship::ConnectAPI::Build.all(
  app_id: app.id,
  version: app_version,
  build_number: build_number
).first
abort("Build #{app_version} (#{build_number}) not found") unless build

group_responses = Spaceship::ConnectAPI.get_beta_groups(
  filter: { app: app.id },
  limit: 200
).all_pages
groups = group_responses.flat_map(&:to_models)
external_groups = groups.reject(&:is_internal_group)
public_groups = external_groups.select(&:public_link_enabled)

selected_group = if requested_group && !requested_group.empty?
                   external_groups.find { |group| group.matches_identifiers?([requested_group]) }
                 elsif public_groups.length == 1
                   public_groups.first
                 end

puts "CEVIZ_BUILD=#{app_version} (#{build_number})"
puts "CEVIZ_PROCESSING_STATE=#{build.processing_state}"
puts "CEVIZ_EXTERNAL_GROUPS=#{external_groups.map(&:name).join('|')}"
puts "CEVIZ_PUBLIC_GROUPS=#{public_groups.map(&:name).join('|')}"
abort("External TestFlight group is ambiguous; set group in #{config_path}") unless selected_group

def build_in_group?(group, build_id)
  group.fetch_builds.any? { |candidate| candidate.id == build_id }
end

before = build_in_group?(selected_group, build.id)
puts "CEVIZ_SELECTED_GROUP=#{selected_group.name}"
puts "CEVIZ_PUBLIC_LINK=#{selected_group.public_link}" if selected_group.public_link
puts "CEVIZ_GROUP_BEFORE=#{before}"

if action == "distribute" && !before
  build.add_beta_groups(beta_groups: [selected_group])
  sleep 3
end

after = build_in_group?(selected_group, build.id)
build = Spaceship::ConnectAPI::Build.all(
  app_id: app.id,
  version: app_version,
  build_number: build_number
).first
detail = build&.build_beta_detail

if action == "distribute" && after && detail&.ready_for_beta_submission?
  build.post_beta_app_review_submission
  sleep 3
  build = Spaceship::ConnectAPI::Build.all(
    app_id: app.id,
    version: app_version,
    build_number: build_number
  ).first
  detail = build&.build_beta_detail
end

puts "CEVIZ_GROUP_AFTER=#{after}"
puts "CEVIZ_INTERNAL_STATE=#{detail&.internal_build_state || 'UNKNOWN'}"
puts "CEVIZ_EXTERNAL_STATE=#{detail&.external_build_state || 'UNKNOWN'}"
puts "CEVIZ_DISTRIBUTION_VERIFIED=#{after}"

abort("Build was not assigned to #{selected_group.name}") unless after
