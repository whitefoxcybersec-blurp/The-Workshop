require "pathname"

module Raven
  class Parser
    attr_reader :rules

    def initialize
      @rules = []
    end

    def parse(path)
      target = Pathname.new(path)
      files = target.directory? ? Dir.glob(target.join("*.rb").to_s).sort : [target.to_s]
      raise ArgumentError, "no rule files found at #{path}" if files.empty?

      files.each do |file|
        source = File.read(file, encoding: "utf-8")
        instance_eval(source, file, 1)
      end
      self
    end

    def rule(name, &definition)
      raise ArgumentError, "rule requires a block" unless definition

      @rules << Rule.new(name, &definition)
    end
  end
end