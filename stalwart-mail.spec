Name:           stalwart-mail
Version:        0.13.4
Release:        1%{?dist}
Summary:        Secure, scalable mail & collaboration server with comprehensive protocol support

License:        AGPL-3.0-only OR LicenseRef-SEL
URL:            https://stalw.art
Source0:        https://github.com/stalwartlabs/stalwart/archive/v%{version}/stalwart-%{version}.tar.gz

BuildRequires:  rust >= 1.70
BuildRequires:  cargo
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  clang
BuildRequires:  clang-devel
BuildRequires:  openssl-devel
BuildRequires:  systemd-devel
BuildRequires:  systemd-rpm-macros
BuildRequires:  pkgconfig(openssl)
BuildRequires:  pkgconfig(systemd)
BuildRequires:  make

# Only build on supported architectures for Rust
ExcludeArch:    i686 s390 %{power64}

# For COPR compatibility
%if 0%{?fedora} >= 36 || 0%{?rhel} >= 9
%bcond_without check
%else
%bcond_with check
%endif

%global debug_package %{nil}

Requires:       glibc
Requires:       openssl
Requires:       systemd
Requires(pre):  shadow-utils
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd

%description
Stalwart is an open-source mail & collaboration server with JMAP, IMAP4, POP3,
SMTP, CalDAV, CardDAV and WebDAV support and a wide range of modern features.
It is written in Rust and designed to be secure, fast, robust and scalable.

Key features include complete email server with JMAP, IMAP4rev2/IMAP4rev1,
POP3, SMTP with built-in DMARC, DKIM, SPF and ARC support, CalDAV/CardDAV
server for contacts and calendars, WebDAV server for file storage, built-in
spam and phishing filter, LDAP and SQL authentication, encryption at rest,
clustering support, and web-based administration interface.

%prep
%autosetup -n stalwart-%{version}

%build
# Set build environment for optimal compilation
export CARGO_TARGET_DIR=%{_builddir}/stalwart-%{version}/target
export RUSTFLAGS="-Ccodegen-units=1 -Clink-dead-code=off"

# Ensure we have a proper Cargo.lock
[ -f Cargo.lock ] || cargo generate-lockfile

# Build with default features (rocks and enterprise)
cargo build --release --verbose --locked

%install
# Create directory structure
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_sysconfdir}/stalwart
install -d %{buildroot}%{_sharedstatedir}/stalwart
install -d %{buildroot}%{_localstatedir}/log/stalwart
install -d %{buildroot}%{_unitdir}
install -d %{buildroot}%{_docdir}/%{name}

# Install binary
install -D -m 755 %{_builddir}/stalwart-%{version}/target/release/stalwart %{buildroot}%{_bindir}/stalwart

# Create and install systemd service file
cat > %{buildroot}%{_unitdir}/stalwart-mail.service << 'EOF'
[Unit]
Description=Stalwart Mail Server
Conflicts=postfix.service sendmail.service exim4.service
ConditionPathExists=%{_sysconfdir}/stalwart/config.toml
After=network-online.target

[Service]
Type=simple
LimitNOFILE=65536
KillMode=process
KillSignal=SIGINT
Restart=on-failure
RestartSec=5
ExecStart=%{_bindir}/stalwart --config=%{_sysconfdir}/stalwart/config.toml
SyslogIdentifier=stalwart
User=stalwart
Group=stalwart
AmbientCapabilities=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
EOF

# Install configuration file
install -m 640 resources/config/config.toml %{buildroot}%{_sysconfdir}/stalwart/config.toml

# Install documentation
install -m 644 README.md %{buildroot}%{_docdir}/%{name}/
install -m 644 CHANGELOG.md %{buildroot}%{_docdir}/%{name}/
install -m 644 CONTRIBUTING.md %{buildroot}%{_docdir}/%{name}/
install -m 644 UPGRADING.md %{buildroot}%{_docdir}/%{name}/
install -m 644 SECURITY.md %{buildroot}%{_docdir}/%{name}/

# Install license files
install -m 644 LICENSES/AGPL-3.0-only.txt %{buildroot}%{_docdir}/%{name}/
install -m 644 LICENSES/LicenseRef-SEL.txt %{buildroot}%{_docdir}/%{name}/

%files
%license %{_docdir}/%{name}/AGPL-3.0-only.txt
%license %{_docdir}/%{name}/LicenseRef-SEL.txt
%doc %{_docdir}/%{name}/README.md
%doc %{_docdir}/%{name}/CHANGELOG.md
%doc %{_docdir}/%{name}/CONTRIBUTING.md
%doc %{_docdir}/%{name}/UPGRADING.md
%doc %{_docdir}/%{name}/SECURITY.md
%config(noreplace) %{_sysconfdir}/stalwart/config.toml
%{_bindir}/stalwart
%{_unitdir}/stalwart-mail.service
%attr(0750,stalwart,stalwart) %dir %{_sharedstatedir}/stalwart
%attr(0750,stalwart,stalwart) %dir %{_localstatedir}/log/stalwart
%attr(0750,stalwart,stalwart) %dir %{_sysconfdir}/stalwart

%pre
# Create stalwart user and group
getent group stalwart >/dev/null || groupadd -r stalwart
getent passwd stalwart >/dev/null || useradd -r -g stalwart -s /usr/sbin/nologin -M -d %{_sharedstatedir}/stalwart -c "Stalwart Mail Server" stalwart

%post
# Initialize configuration if this is a fresh install
if [ $1 -eq 1 ]; then
    # Run stalwart --init to create initial configuration (run as root, then fix ownership)
    %{_bindir}/stalwart --init %{_sharedstatedir}/stalwart >/dev/null 2>&1 || true
    # Ensure proper ownership of data directories
    chown -R stalwart:stalwart %{_sharedstatedir}/stalwart %{_localstatedir}/log/stalwart 2>/dev/null || true
    chmod 640 %{_sysconfdir}/stalwart/config.toml 2>/dev/null || true
    chown stalwart:stalwart %{_sysconfdir}/stalwart/config.toml 2>/dev/null || true
fi
%systemd_post stalwart-mail.service

%preun
%systemd_preun stalwart-mail.service

%postun
%systemd_postun_with_restart stalwart-mail.service
# Remove user and group on complete removal
if [ $1 -eq 0 ]; then
    # Clean up data directories on uninstall
    rm -rf %{_sharedstatedir}/stalwart/* 2>/dev/null || true
    getent passwd stalwart >/dev/null && userdel stalwart >/dev/null 2>&1 || true
    getent group stalwart >/dev/null && groupdel stalwart >/dev/null 2>&1 || true
fi

%changelog
* Mon Sep 30 2024 mdecimus <hello@stalw.art> - 0.13.4-1
- Security fix: IMAP unbounded memory allocation in request parser (CVE-2025-61600)
- Security fix: CalDAV limit recurrence expansions in calendar reports (CVE-2025-59045)
- Fixed IMAP wrong permission checked for GETACL
- Fixed JMAP references to previous method fail when there are no results
- Fixed JMAP enforce quota checks on Blob/copy
- Fixed JMAP Mailbox/get fails without accountId argument
- Fixed iTIP include date properties in REPLY messages
- Fixed OIDC do not set username field if same as email field
- Fixed telemetry calculateMetrics housekeeper task
- Changed JMAP protocol layer rewrite for zero-copy deserializations
