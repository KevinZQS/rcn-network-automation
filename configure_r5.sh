#!/bin/bash
R5=$(docker inspect clab-rcn-lab2-R5 --format '{{.NetworkSettings.Networks.clab.IPAddress}}')
echo "[R5] found at $R5"
ssh-keygen -f ~/.ssh/known_hosts -R "$R5" 2>/dev/null
S="sshpass -p admin ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR admin@$R5"
echo "[R5] waiting for SSH..."
for i in $(seq 1 20); do
    $S "echo READY" 2>/dev/null | grep -q READY && break
    echo "  attempt $i/20..."
    sleep 15
done
echo "[R5] bringing up ports"
for p in Ethernet0 Ethernet4 Ethernet8; do $S "sudo config interface startup $p"; done
sleep 5
echo "[R5] addressing"
$S "sudo config interface ip add Loopback0 10.255.0.5/32"
$S "sudo config interface ip add Loopback0 2001:db8:ffff::5/128"
$S "sudo config interface ip add Ethernet0 10.20.0.22/30"
$S "sudo config interface ip add Ethernet0 2001:db8:2000:6::2/64"
$S "sudo config interface ip add Ethernet4 10.20.0.26/30"
$S "sudo config interface ip add Ethernet4 2001:db8:2000:7::2/64"
$S "sudo config interface ip add Ethernet8 10.30.0.1/24"
$S "sudo config interface ip add Ethernet8 2001:db8:3000:100::1/64"
echo "[R5] BGP"
$S 'vtysh -c "configure terminal" -c "no router bgp 65100" -c "router bgp 65100" -c "bgp router-id 10.255.0.5" -c "no bgp ebgp-requires-policy" -c "no bgp default ipv4-unicast" -c "neighbor 10.20.0.21 remote-as 65000" -c "neighbor 10.20.0.25 remote-as 65000" -c "neighbor 2001:db8:2000:6::1 remote-as 65000" -c "neighbor 2001:db8:2000:7::1 remote-as 65000" -c "address-family ipv4 unicast" -c "network 10.30.0.0/24" -c "neighbor 10.20.0.21 activate" -c "neighbor 10.20.0.25 activate" -c "exit-address-family" -c "address-family ipv6 unicast" -c "maximum-paths 1" -c "network 2001:db8:3000:100::/64" -c "neighbor 2001:db8:2000:6::1 activate" -c "neighbor 2001:db8:2000:7::1 activate" -c "exit-address-family" -c "end"'
sleep 10
echo "[R5] fixing management route"
$S "sudo ip route del default dev eth0 2>/dev/null; sudo ip route add 172.20.20.0/24 via 10.0.0.2 dev eth0 2>/dev/null"
sleep 3
echo "[R5] removing competing IPv6 mgmt routes"
$S "sudo ip -6 route del default via 2001:db8::1 dev eth0" 2>/dev/null
$S "sudo ip -6 route flush proto ra" 2>/dev/null
$S "sudo config save -y"
echo "[R5] verification:"
$S 'vtysh -c "show bgp summary"'
$S 'vtysh -c "show ip route" | grep "0.0.0.0/0"'
$S 'vtysh -c "show ipv6 route" | grep "::/0"'