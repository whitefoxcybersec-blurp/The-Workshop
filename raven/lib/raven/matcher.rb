module Raven
  class Matcher
    def self.matches?(event, source: nil, conditions: {}, predicate: nil)
      return false if source && normalize(value(event, :source)) != normalize(source)

      conditions_match = conditions.all? do |field, expected|
        normalize(value(event, field)) == normalize(expected)
      end
      return false unless conditions_match

      predicate.nil? || predicate.call(event)
    end

    def self.value(event, field)
      return event.public_send(field) if !event.is_a?(Hash) && event.respond_to?(field)
      return nil unless event.respond_to?(:key?)

      symbol = field.to_sym
      return event[symbol] if event.key?(symbol)
      return event[field.to_s] if event.key?(field.to_s)

      nil
    end

    def self.normalize(value)
      value.is_a?(Symbol) ? value.to_s : value
    end
    private_class_method :normalize
  end
end