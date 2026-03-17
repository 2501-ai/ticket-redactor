#!/usr/bin/env python3
"""Generate a realistic sample CSV of MSP client tickets with PII."""

import csv
import random
import sys

FIRST_NAMES = [
    "James", "Maria", "Jean-Pierre", "Yuki", "Priya", "Carlos", "Anna",
    "Mohammed", "Sophie", "Raj", "Emily", "Hans", "Fatima", "Luca",
    "Olga", "David", "Chen", "Isabelle", "Tomasz", "Aisha",
]

LAST_NAMES = [
    "Smith", "Dubois", "Tanaka", "Patel", "Rodriguez", "Weber", "Al-Hassan",
    "Rossi", "Kowalski", "Chen", "Brown", "Muller", "Nakamura", "Sharma",
    "Johansson", "Garcia", "Kim", "Novak", "O'Brien", "Santos",
]

COMPANIES = [
    "Acme Corp", "Globex Industries", "Initech Solutions", "Umbrella Ltd",
    "Nexus Financial", "Meridian Healthcare", "Atlas Logistics",
    "Pinnacle Energy", "Vertex Telecom", "Horizon Media Group",
]

DOMAINS = [
    "acmecorp.com", "globex.eu", "initech.io", "umbrella.co.uk",
    "nexusfin.com", "meridian-health.org", "atlas-logistics.de",
    "pinnacle-energy.fr", "vertex-telecom.net", "horizonmedia.com",
]

AGENTS = [
    "Alice Martin", "Bob Nguyen", "Clara Fischer", "Derek Singh",
    "Eva Kowalska", "Frank Moreau", "Grace Yamamoto", "Hugo Fernandez",
]

HOSTNAMES = [
    "srv-prod-01.internal", "srv-db-02.internal", "fw-gw-01.dmz.local",
    "app-web-03.cloud.local", "dc-ad-01.corp.local", "mail-relay-01.internal",
    "vpn-gw-02.edge.local", "node-k8s-05.cluster.local",
]

SUBNETS = ["192.168.1", "10.0.0", "172.16.0", "10.10.5", "203.0.113"]

ISSUE_TEMPLATES = [
    "User {name} reported VPN connectivity drops when connecting to {hostname}. "
    "Please check firewall rules for {ip}. Contact: {email} / {phone}.",

    "Password reset requested for {name} ({email}). Account locked after "
    "multiple failed attempts from {ip}. Manager {manager} approved the reset.",

    "Workstation {mac} assigned to {name} is not receiving DHCP lease from {ip}. "
    "Tried releasing/renewing. IT contact: {email}.",

    "{name} from {company} reports slow response on {hostname}. Traceroute "
    "shows latency spike at {ip}. Escalate to network team. Ref: {email}.",

    "Security alert: unauthorized access attempt on {hostname} from {ip}. "
    "Account owner: {name} ({email}). SSN on file: {ssn}. Verify identity before proceeding.",

    "New employee onboarding for {name} at {company}. Setup email {email}, "
    "VPN access to {hostname}, assign IP from {subnet}.0/24 range. Badge ID pending.",

    "Client {name} ({company}) reported IBAN {iban} incorrectly charged. "
    "Transaction from {ip}. Follow up at {email} or {phone}.",

    "Printer on {ip} (MAC {mac}) not reachable from {name}'s workstation. "
    "Checked switch port, no link. Contact {email} to schedule on-site visit.",

    "Backup failure on {hostname} at 03:00 UTC. {name} from {company} needs "
    "recovery of files from {ip}. Notify {manager} at {manager_email}.",

    "Phishing email forwarded by {name} ({email}). Originated from {ip}, "
    "spoofing {company} domain. Block sender and scan {hostname} for compromise.",

    "{name} at {company} needs access to {hostname} for the audit. "
    "Current IP whitelist: {ip}. Approve via {manager} ({manager_email}). Phone: {phone}.",

    "Certificate expiring on {hostname} in 7 days. Owner: {name} ({email}). "
    "Renew and deploy. Load balancer at {ip} also needs update.",
]

PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["Open", "In Progress", "Waiting on Client", "Resolved", "Escalated"]
CATEGORIES = [
    "Network", "Security", "Access Management", "Hardware",
    "Software", "Backup/Recovery", "Email", "VPN",
]


def random_phone():
    formats = [
        "+1 {}-{}-{}".format(
            random.randint(200, 999), random.randint(100, 999), random.randint(1000, 9999)
        ),
        "+33 6 {} {} {} {}".format(
            random.randint(10, 99), random.randint(10, 99),
            random.randint(10, 99), random.randint(10, 99),
        ),
        "+44 20 {} {}".format(random.randint(1000, 9999), random.randint(1000, 9999)),
        "+49 170 {}".format(random.randint(1000000, 9999999)),
        "+91 {} {}".format(random.randint(10000, 99999), random.randint(10000, 99999)),
    ]
    return random.choice(formats)


def random_mac():
    return ":".join(f"{random.randint(0, 255):02X}" for _ in range(6))


def random_ip():
    subnet = random.choice(SUBNETS)
    return f"{subnet}.{random.randint(1, 254)}"


def random_ssn():
    return f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"


def random_iban():
    country = random.choice(["FR", "DE", "GB", "ES", "IT", "NL"])
    digits = "".join(str(random.randint(0, 9)) for _ in range(22))
    return f"{country}{random.randint(10, 99)}{digits}"


def generate_row(ticket_num):
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"
    company_idx = random.randint(0, len(COMPANIES) - 1)
    company = COMPANIES[company_idx]
    domain = DOMAINS[company_idx]
    email = f"{first.lower()}.{last.lower()}@{domain}"

    mgr_first = random.choice(FIRST_NAMES)
    mgr_last = random.choice(LAST_NAMES)
    manager = f"{mgr_first} {mgr_last}"
    manager_email = f"{mgr_first.lower()}.{mgr_last.lower()}@{domain}"

    template = random.choice(ISSUE_TEMPLATES)
    description = template.format(
        name=name,
        email=email,
        phone=random_phone(),
        company=company,
        hostname=random.choice(HOSTNAMES),
        ip=random_ip(),
        mac=random_mac(),
        ssn=random_ssn(),
        iban=random_iban(),
        subnet=random.choice(SUBNETS),
        manager=manager,
        manager_email=manager_email,
    )

    return [
        f"TK-{ticket_num:04d}",
        name,
        email,
        random_phone(),
        company,
        random.choice(PRIORITIES),
        random.choice(STATUSES),
        random.choice(CATEGORIES),
        description,
        random.choice(AGENTS),
        f"2026-{random.randint(1, 3):02d}-{random.randint(1, 28):02d}",
    ]


def main():
    num_rows = int(sys.argv[1]) if len(sys.argv) > 1 else 75
    output = sys.argv[2] if len(sys.argv) > 2 else "sample_tickets.csv"

    header = [
        "ticket_id", "client_name", "client_email", "client_phone",
        "company", "priority", "status", "category",
        "description", "assigned_to", "created_date",
    ]

    random.seed(42)  # reproducible

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for i in range(1, num_rows + 1):
            writer.writerow(generate_row(i))

    print(f"Generated {num_rows} rows -> {output}")


if __name__ == "__main__":
    main()
