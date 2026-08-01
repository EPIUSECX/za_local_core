#!/usr/bin/env bash

set -euo pipefail

start_redis_port() {
	local port="$1"
	if redis-cli -p "$port" ping >/dev/null 2>&1; then
		return
	fi
	redis-server --daemonize yes --port "$port" --save "" --appendonly no --dir /tmp
	for _ in {1..20}; do
		redis-cli -p "$port" ping >/dev/null 2>&1 && return
		sleep 1
	done
	echo "Redis did not start on port $port" >&2
	exit 1
}

get_localisation_dependency() {
	local app="$1"
	bench get-app "$app" "https://github.com/EPIUSECX/$app.git"
}

sudo apt-get update
sudo apt-get install -y libcups2-dev libmariadb-dev mariadb-client pkg-config redis-server
python -m pip install frappe-bench

bench init --skip-assets --python "$(command -v python)" --frappe-branch "$FRAPPE_BRANCH" /home/runner/frappe-bench
cd /home/runner/frappe-bench

bench get-app erpnext https://github.com/frappe/erpnext --branch "$ERPNEXT_BRANCH" --resolve-deps
bench get-app hrms https://github.com/frappe/hrms --branch "$HRMS_BRANCH"

install_apps=(erpnext hrms)
build_apps=(frappe erpnext hrms)
if [[ "$APP_NAME" != "za_local_core" ]]; then
	get_localisation_dependency za_local_core
	install_apps+=(za_local_core)
	build_apps+=(za_local_core)
fi
if [[ "$APP_NAME" == "za_local_workplace" ]]; then
	get_localisation_dependency za_local_payroll
	install_apps+=(za_local_payroll)
	build_apps+=(za_local_payroll)
fi

bench get-app --overwrite "$APP_NAME" "$GITHUB_WORKSPACE"
install_apps+=("$APP_NAME")
build_apps+=("$APP_NAME")
bench setup requirements --dev

start_redis_port 11000
start_redis_port 13000

IFS=,
CI=Yes bench build --apps "${build_apps[*]}"
unset IFS

bench new-site test_site \
	--db-host 127.0.0.1 \
	--db-port 3306 \
	--mariadb-root-password root \
	--admin-password admin \
	--no-mariadb-socket

declare -A installed
for app in "${install_apps[@]}"; do
	if [[ -z "${installed[$app]:-}" ]]; then
		bench --site test_site install-app "$app"
		installed[$app]=1
	fi
done
