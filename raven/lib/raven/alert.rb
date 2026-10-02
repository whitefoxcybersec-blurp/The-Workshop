require "securerandom"
require "time"

module Raven
  class Alert
    attr_reader :id, :rule_name, :description, :severity, :group, :count,
                :timestamp, :events

    def initialize(rule:, context:)
      @id = SecureRandom.uuid
      @rule_name = rule.name
      @description = rule.description_text
      @severity = rule.severity_level
      @group = context.group
      @count = context.count
      @timestamp = context.timestamp.utc
      @events = context.events
    end

    def to_h
      {
        id: @id,
        rule: @rule_name,
        description: @description,
        severity: @severity,
        group: @group,
        count: @count,
        timestamp: @timestamp.iso8601(6),
        events: @events
      }
    end
  end
end