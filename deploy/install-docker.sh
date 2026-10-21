#!/bin/sh
set -eu
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker version --format '{{.Server.Version}}'
  exit 0
fi
. /etc/os-release
[ "$ID" = ubuntu ] || { echo 'This bootstrap supports Ubuntu only.' >&2; exit 1; }
for package in docker.io docker-compose containerd runc; do
  if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
    echo "Existing $package requires a reviewed migration; no packages removed." >&2
    exit 1
  fi
done
apt-get -o Acquire::Retries=3 update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl --retry 3 --retry-all-errors --connect-timeout 10 --max-time 60 -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get -o Acquire::Retries=3 update
DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
docker version --format '{{.Server.Version}}'
docker compose version
