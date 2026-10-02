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