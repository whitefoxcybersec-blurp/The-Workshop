module Raven
  class Duration
    attr_reader :seconds

    def initialize(seconds)
      @seconds = Float(seconds)
      raise ArgumentError, "duration must be positive" unless @seconds.positive?
    end
  end

  module NumericDuration
    def seconds
      Raven::Duration.new(self)
    end

    alias second seconds
  end
end

Numeric.include(Raven::NumericDuration) unless Numeric.ancestors.include?(Raven::NumericDuration)