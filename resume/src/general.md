---
name: Steven Shine
title: Systems Engineer | Windows, Identity & Infrastructure Automation
headline: Systems Engineer II | Active Directory · Windows Server · Microsoft 365 / Entra ID · VMware · Citrix · PowerShell automation
location: Denver, CO
email: steven.shine@gmail.com
website: stevenshine.info
linkedin: linkedin.com/in/stevenshine
github: github.com/sshinenet
variant: general
target: General systems / infrastructure engineering roles (deployed to stevenshine.info)
highlights: 9 domain controllers rebuilt to Server 2025, no hostname or IP changed | 50+ patch and CVE changes across 3 years | ~1,500 tickets and 147 CAB changes, 2-day median | 40 PowerShell automation modules maintained
---

## Summary

Systems engineer with 15 years in IT, the last three as the primary Windows, Active Directory, and identity engineer for a two-forest estate at a Denver metro based software company. Runs infrastructure through formal change control and replaces recurring manual work with tested PowerShell automation.

## Experience

### Systems Engineer II | Denver metro based software company
Nov 2023 – Present · Denver, CO
- Own two Active Directory forests (nine domain controllers across two datacenters, Azure, and DMZs), Windows Server on VMware vSphere 8, Citrix, Microsoft 365 and Entra ID hybrid identity, PKI, DNS, and SMTP.
- Led the rebuild of nine domain controllers from Server 2016 to 2025 with every hostname and IP preserved and no domain-wide interruption; resolved two vendor integration outages in-window and wrote both RCAs.
- Run the patch and CVE lifecycle for NetScaler ADC, ESXi, Windows Server, and firmware: 50+ changes over three years, including critical (CVSS 9+) fixes inside single change windows via scripted preflight and rolling upgrades.
- Built and maintain the team's ~40-module PowerShell library (offboarding, AD lifecycle, Exchange Online, VMware, Citrix, DNS, PKI); automation cut routine access and Citrix tickets from 45% to 29% of my volume, 2024 to 2026.
- Wrote Microsoft Graph automation under least-privilege Entra app registrations: recurring-meeting backfill for new hires, Teams federation controls, and call-record forensics for a vishing incident.
- Audited DFS permissions across 18,560 folders, identifying 162 inheritance breaks and 344 direct-user Full Control grants to scope a role-based access cleanup; migrated the fleet to Windows LAPS.
- Replaced anonymous SMTP relay with four authenticated STARTTLS listeners and SendGrid egress for printers, devices, and applications.
- Own the quarterly disaster-recovery restore validation since 2024 (backup monitoring, media handling, restore proof).
- Closed ~1,500 tickets and 147 CAB-approved changes with a two-day median time to resolution; 97% resolved.

### Infrastructure Engineer | Poppulo
Apr 2021 – May 2023 · Denver, CO
- Ran network, server, and storage operations for a SaaS employee-communications and digital-signage platform, handled client escalations, and carried the after-hours on-call rotation.
- Replaced hand-built environments with Terraform and Ansible builds driven from the AWS CLI.

### System Administrator | Four Winds Interactive
Nov 2019 – Apr 2021 · Denver, CO
- Deployed 20+ Windows and Linux systems on AWS and Azure for internal and production use.
- Deployed Okta SSO integrations with enterprise customers connecting to the production platform.
- Built the Confluence knowledge base and Jira change-approval workflow that became the team's standard change process.

### Associate System Administrator | Four Winds Interactive
Jan 2015 – Nov 2019 · Denver, CO
- Managed 100+ on-premises, colocation, and cloud servers.
- Rolled out Slack, full-disk encryption on every workstation, and the operational controls behind SOC 2 compliance across 450+ users.
- Migrated an acquired company's user base into the environment while providing Tier II support for a mixed Apple and Windows fleet of 500+ local and remote employees.

### Senior Hardware Specialist | Four Winds Interactive
2011 – 2015 · Denver, CO
- Progressed from Field Services Technician (2011) through Hardware Specialist to Senior Hardware Specialist (2014).
- Delivered and supported digital-signage deployments for thousands of endpoints across hundreds of customers, integrating video capture, Kinect, and touch-screen hardware on Windows, Android, macOS, and iOS.

## Projects

### Cloud Resume Challenge | stevenshine.info
2023 – 2026
- Static site on AWS (S3 behind CloudFront with Origin Access Control, ACM certificate, Route 53) with a serverless visitor counter (API Gateway, Python Lambda, DynamoDB atomic increment).
- Entire stack defined in Terraform with remote S3 state and native locking; GitHub Actions deploys through OIDC role assumption with no stored cloud credentials and a gated production environment.
- Backend covered by pytest with moto, frontend by Node's built-in test runner with zero npm dependencies.

## Skills

- **Directory & identity:** Active Directory (multi-forest, RODC, schema extension, FSMO, DFSR/SYSVOL), Group Policy, Windows LAPS, gMSA, Kerberos/NTLM hardening, Microsoft Entra ID, Entra Connect, Okta and Duo SAML, RADIUS, Cisco ISE
- **Windows & virtualization:** Windows Server 2012 R2–2025, VMware vSphere/ESXi 8, vCenter, PowerCLI, Citrix Virtual Apps and Desktops LTSR, Citrix Provisioning, NetScaler ADC (HA, nFactor, SAML, load balancing)
- **Cloud & Microsoft 365:** Microsoft Azure (IaaS, Functions, Az PowerShell), AWS (S3, CloudFront, Lambda, DynamoDB, API Gateway, IAM/OIDC), Exchange Online, Microsoft Graph API, SharePoint, Teams, Purview
- **Security & PKI:** AD Certificate Services, Authenticode code signing, mutual TLS, OpenSSL, Carbon Black App Control, CrowdStrike, Windows Event Forwarding, CVE analysis and remediation, least-privilege design
- **Automation & code:** PowerShell 5.1/7 (modules, remoting, WinForms, Pester), Python, Bash, C#/.NET, T-SQL, REST APIs, Terraform, Ansible, Git, GitHub Actions
- **Infrastructure services:** Windows DNS/DHCP, DFS Namespaces, IIS and IIS SMTP, SendGrid, SQL Server Always On, SolarWinds Orion, Palo Alto User-ID, Commvault
- **Practices:** ITIL change management and CAB, runbook and operator run-sheet authoring, root-cause analysis, disaster-recovery testing, audit evidence collection

## Education

### BA, General Studies | Louisiana State University
May 2009
