require_relative "lib/raven/version"

Gem::Specification.new do |spec|
  spec.name = "raven-security-dsl"
  spec.version = Raven::VERSION
  spec.summary = "A Ruby DSL for temporal security event rules"
  spec.description = "Evaluate declarative security rules against JSONL or ARGUS event timelines."
  spec.authors = ["RAVEN contributors"]
  spec.files = Dir["lib/**/*.rb", "bin/*", "rules/**/*.rb", "README.md"]
  spec.bindir = "bin"
  spec.executables = ["raven"]
  spec.require_paths = ["lib"]
  spec.required_ruby_version = ">= 3.1"
end