module Raven
  class Rule
    SEVERITIES = %i[low medium high critical].freeze

    attr_reader :name, :description_text, :severity_level, :conditions,
                :group_fields, :threshold_count, :within_seconds

    def initialize(name, &definition)
      @name = name.to_s.strip
      @description_text = ""
      @source_name = nil
      @conditions = {}
      @group_fields = []
      @threshold_count = 1
      @within_seconds = 60.0
      @severity_level = :medium
      @matcher = nil
      @callback = nil
      instance_eval(&definition) if definition
      validate!
    end

    def description(text = nil)
      @description_text = text.to_s unless text.nil?
      @description_text
    end

    def source(name = nil)
      @source_name = name unless name.nil?
      @source_name
    end

    def match(&predicate)
      raise ArgumentError, "match requires a block" unless predicate

      @matcher = predicate
    end

    def where(conditions = nil, **keywords)
      values = conditions ? conditions.to_h : {}
      values.merge!(keywords)
      values.each { |field, expected| @conditions[field.to_s] = expected }
      @conditions
    end

    def group_by(*fields)
      @group_fields = fields.flatten.map(&:to_s)
    end

    def threshold(count = nil)
      @threshold_count = Integer(count) unless count.nil?
      @threshold_count
    end

    def within(duration = nil)
      unless duration.nil?
        @within_seconds = duration.is_a?(Duration) ? duration.seconds : Float(duration)
      end
      @within_seconds
    end

    def severity(level = nil)
      @severity_level = level.to_sym unless level.nil?
      @severity_level
    end

    def on_match(&callback)
      raise ArgumentError, "on_match requires a block" unless callback

      @callback = callback
    end

    def matches?(event)
      Matcher.matches?(
        event,
        source: @source_name,
        conditions: @conditions,
        predicate: @matcher
      )
    end

    def group_for(event)
      return :global if @group_fields.empty?

      values = @group_fields.to_h { |field| [field, Matcher.value(event, field)] }
      @group_fields.length == 1 ? values.fetch(@group_fields.first) : values
    end

    def dispatch(context)
      instance_exec(context, &@callback) if @callback
    end

    def alert(context)
      context.alert
    end

    private

    def validate!
      raise ArgumentError, "rule name cannot be empty" if @name.empty?
      raise ArgumentError, "threshold must be positive" unless @threshold_count.positive?
      raise ArgumentError, "within must be positive" unless @within_seconds.positive?
      raise ArgumentError, "invalid severity: #{@severity_level}" unless SEVERITIES.include?(@severity_level)
    end
  end
end