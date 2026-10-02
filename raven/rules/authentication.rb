rule "Successful Root Login" do
  description "A root login succeeded"

  where event: "authentication", user: "root", result: "success"
  group_by :src_ip
  threshold 1
  within 60.seconds
  severity :high
end