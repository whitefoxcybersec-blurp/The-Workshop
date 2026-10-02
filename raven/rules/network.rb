rule "Repeated Network Connections" do
  description "Repeated network connections from one source IP"

  where event: "network_connection"
  group_by :src_ip
  threshold 20
  within 60.seconds
  severity :medium
end