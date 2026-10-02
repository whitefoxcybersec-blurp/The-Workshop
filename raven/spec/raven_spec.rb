require "spec_helper"

RSpec.describe Raven do
  def rule(threshold: 10, within: 60, &block)
    Raven::Rule.new("test rule") do
      description "test description"
      where event: "authentication", result: "failed"
      group_by :src_ip
      threshold threshold
      within within.seconds
      severity :high
      instance_eval(&block) if block
    end
  end

  def event(second, src_ip: "192.168.1.50", result: "failed")
    {
      "timestamp" => Time.utc(2026, 10, 2, 13, 37, second).iso8601,
      "source" => "linux",
      "event" => "authentication",
      "service" => "ssh",
      "src_ip" => src_ip,
      "result" => result
    }
  end

  it "builds rules through the block DSL" do
    parsed = Raven::Parser.new.parse(File.expand_path("../rules/ssh.rb", __dir__))

    expect(parsed.rules.map(&:name)).to eq(["SSH Bruteforce"])
    expect(parsed.rules.first.threshold_count).to eq(10)
    expect(parsed.rules.first.within_seconds).to eq(60.0)
  end

  it "alerts once when a group reaches its threshold inside the time window" do
    engine = Raven::Engine.new([rule])

    9.times { |second| expect(engine.process(event(second))).to be_empty }
    alert = engine.process(event(9)).fetch(0)
    expect(alert.rule_name).to eq("test rule")
    expect(alert.group).to eq("192.168.1.50")
    expect(alert.count).to eq(10)
    expect(alert.severity).to eq(:high)
    expect(engine.process(event(10))).to be_empty
  end

  it "keeps groups for different source IPs separate" do
    engine = Raven::Engine.new([rule(threshold: 2)])

    expect(engine.process(event(0, src_ip: "192.168.1.50"))).to be_empty
    expect(engine.process(event(1, src_ip: "192.168.1.51"))).to be_empty
    expect(engine.process(event(2, src_ip: "192.168.1.50")).first.group).to eq("192.168.1.50")
  end

  it "rearms after the previous window expires" do
    engine = Raven::Engine.new([rule(threshold: 2, within: 5)])

    expect(engine.process(event(0))).to be_empty
    expect(engine.process(event(1)).length).to eq(1)
    expect(engine.process(event(10))).to be_empty
    expect(engine.process(event(11)).length).to eq(1)
  end

  it "invokes the callback with a context containing its alert" do
    captured = nil
    callback_rule = rule(threshold: 1) do
      on_match { |context| captured = alert(context) }
    end

    Raven::Engine.new([callback_rule]).process(event(0))
    expect(captured).to be_a(Raven::Alert)
    expect(captured.count).to eq(1)
  end

  it "supports an ARGUS event hash with string keys" do
    engine = Raven::Engine.new([rule(threshold: 1)])
    alert = engine.process(event(0)).fetch(0)

    expect(alert.events.first["source"]).to eq("linux")
  end
end