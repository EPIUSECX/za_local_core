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

authorise_private_repositories() {
	# The localisation repositories are private. A workflow's GITHUB_TOKEN only
	# grants access to its own repository, so cloning a sibling needs an explicit
	# credential. Configure it through insteadOf so the token never reaches a
	# command line or a build log.
	if [[ -z "${ZA_LOCAL_CI_TOKEN:-}" ]]; then
		cat >&2 <<-'MISSING'
			This job must clone a sibling localisation repository, and those
			repositories are private.

			Add a repository or organisation secret named ZA_LOCAL_CI_TOKEN holding a
			token with read access to the EPIUSECX localisation repositories, and pass
			it to this step, or make those repositories public.
		MISSING
		exit 1
	fi
	git config --global \
		url."https://x-access-token:${ZA_LOCAL_CI_TOKEN}@github.com/".insteadOf \
		"https://github.com/"
}

get_localisation_dependency() {
	local app="$1"
	local ref="$2"
	authorise_private_repositories
	bench get-app "$app" "https://github.com/EPIUSECX/$app.git" --branch "$ref"
}

sudo apt-get update
sudo apt-get install -y libcups2-dev libmariadb-dev mariadb-client pkg-config redis-server
python -m pip install frappe-bench

bench init --skip-assets --python "$(command -v python)" --frappe-branch "$FRAPPE_BRANCH" /home/runner/frappe-bench
cd /home/runner/frappe-bench

bench get-app erpnext https://github.com/frappe/erpnext --branch "$ERPNEXT_BRANCH" --resolve-deps

install_apps=(erpnext)
build_apps=(frappe erpnext)
if [[ "$APP_NAME" == "za_local_payroll" || "$APP_NAME" == "za_local_workplace" ]]; then
	bench get-app hrms https://github.com/frappe/hrms --branch "$HRMS_BRANCH"
	install_apps+=(hrms)
	build_apps+=(hrms)
fi
if [[ "$APP_NAME" != "za_local_core" ]]; then
	get_localisation_dependency za_local_core "${ZA_LOCAL_CORE_REF:-main}"
	install_apps+=(za_local_core)
	build_apps+=(za_local_core)
fi
if [[ "$APP_NAME" == "za_local_workplace" ]]; then
	get_localisation_dependency za_local_payroll "${ZA_LOCAL_PAYROLL_REF:-main}"
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

bench --site test_site migrate
first_core_state="$(bench --site test_site execute za_local_core.migration.release.core_state_fingerprint | tail -n 1)"
bench --site test_site migrate
second_core_state="$(bench --site test_site execute za_local_core.migration.release.core_state_fingerprint | tail -n 1)"
if [[ "$first_core_state" != "$second_core_state" ]]; then
	echo "Core-owned migration state changed on the second migrate" >&2
	echo "first:  $first_core_state" >&2
	echo "second: $second_core_state" >&2
	exit 1
fi
bench --site test_site execute za_local_core.migration.release.assert_legacy_app_absent
