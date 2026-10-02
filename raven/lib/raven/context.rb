module Raven
  class Context
    attr_reader :rule, :group, :events, :timestamp
    attr_accessor :alert

    def initialize(rule:, group:, events:, timestamp:)
      @rule = rule
      @group = group
      @events = events
      @timestamp = timestamp
      @alert = nil
    end

    def count
      @events.length
    end

    def event
      @events.last
    end
  end
end