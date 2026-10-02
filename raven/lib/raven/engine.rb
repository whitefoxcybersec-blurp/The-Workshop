require "time"

module Raven
  class Engine
    Entry = Struct.new(:timestamp, :event)

    attr_reader :alerts

    def initialize(rules)
      @rules = rules
      @windows = {}
      @alerts = []
    end

    def process(event)
      raise ArgumentError, "event must be a Hash" unless event.is_a?(Hash)

      timestamp = event_time(event)
      generated = []
      @rules.each do |rule|
        next unless rule.matches?(event)

        group = rule.group_for(event)
        state_key = [rule.object_id, group]
        state = (@windows[state_key] ||= { entries: [], fired: false })
        entries = state[:entries]
        cutoff = timestamp - rule.within_seconds
        entries.delete_if { |entry| entry.timestamp < cutoff }
        active_before = entries.count { |entry| entry.timestamp <= timestamp }
        state[:fired] = false if active_before.zero?

        entries << Entry.new(timestamp, event)
        entries.sort_by!(&:timestamp)
        window_entries = entries.select { |entry| entry.timestamp <= timestamp }
        next if window_entries.length < rule.threshold_count || state[:fired]

        context = Context.new(
          rule: rule,
          group: group,
          events: window_entries.map(&:event),
          timestamp: timestamp
        )
        alert = Alert.new(rule: rule, context: context)
        context.alert = alert
        rule.dispatch(context)
        state[:fired] = true
        @alerts << alert
        generated << alert
      end
      generated
    end

    private

    def event_time(event)
      value = event[:timestamp] || event["timestamp"]
      return Time.now.utc if value.nil?
      return Time.at(value).utc if value.is_a?(Numeric)
      return value.utc if value.is_a?(Time)

      Time.parse(value.to_s).utc
    rescue ArgumentError, TypeError
      raise ArgumentError, "event timestamp must be ISO-8601 text or Unix time"
    end
  end
end