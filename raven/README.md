# RAVEN

RAVEN is a Ruby DSL and temporal rule engine for defensive event detection. Rules
are Ruby blocks, not YAML predicates: the parser evaluates each rule file in a
small DSL context, then the engine groups matching events and applies time windows.

## Setup

Requires Ruby 3.1 or newer and Bundler.

```sh
cd raven
bundle install
bundle exec rspec
```

## Run rules against JSONL

```sh
bin/raven --rules rules --input samples/auth.jsonl
cat events.jsonl | bin/raven --rules rules
```

Each alert is emitted as one JSON object on stdout. Invalid JSONL lines are
reported on stderr and skipped.

## DSL

```ruby
rule "SSH Bruteforce" do
  description "Repeated SSH authentication failures from one source IP"

  where event: "authentication", result: "failed"
  match do |event|
    event["service"] == "ssh" || event.fetch("message", "").match?(/\bsshd\b/i)
  end

  group_by :src_ip
  threshold 10
  within 60.seconds
  severity :high

  on_match do |context|
    alert context
  end
end
```

`source` and `where` apply exact field filters; `match` adds a Ruby predicate.
`group_by` keeps independent temporal windows per key. A rule fires once while
its threshold remains active, then can fire again after its matching events age
out. The `seconds` numeric helper is loaded by `require "raven"`.

Rule files are executable Ruby code. Only load rule files you trust.

## ARGUS bridge

RAVEN can fetch normalized events from ARGUS's read-only timeline API:

```sh
bin/raven --rules rules --argus-url http://127.0.0.1:8765
```

It reads up to 2,000 timeline entries, evaluates only event records, and keeps
rule evaluation in the Ruby process. The event contract is compatible with
ARGUS JSONL fields (`timestamp`, `source`, `event`, `src_ip`, `user`, `result`).