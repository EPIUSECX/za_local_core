// Desk entry point for publishing the federated localisation guides into
// Frappe Wiki. Publication is deliberately manual -- it writes website content,
// so it is not something an install or migrate should do behind the user's back.

// The HTTP method is stated on every call. frappe.call defaults to POST, and a
// method the endpoint does not allow is rejected as "Not permitted", which reads
// like a role problem and is not one.
const STATUS_METHOD = "za_local_core.practitioner_guide.stage.get_guide_status";
const PUBLISH_METHOD = "za_local_core.practitioner_guide.stage.publish_practitioner_guide";

frappe.pages["sa-localisation-guides"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("SA Localisation Guides"),
		single_column: true,
	});

	const container = $('<div class="za-guides"></div>').appendTo(page.main);

	page.set_secondary_action(__("Refresh"), () => render(page, container));

	render(page, container);
};

function render(page, container) {
	container.html(`<div class="text-muted">${__("Loading…")}</div>`);
	frappe
		.call({ method: STATUS_METHOD, type: "GET" })
		.then((response) => {
			const status = response.message || {};
			// No Wiki to publish into, or no right to publish, means no button --
			// not a button that fails when pressed.
			if (status.wiki_installed && status.can_publish) {
				page.set_primary_action(__("Publish Guides"), () => publish(page, container));
			} else {
				page.clear_primary_action();
			}
			container.empty();
			container.append(intro(status));
			container.append(contributors(status));
			container.append(spaces(status));
		})
		.catch(() => {
			container.html(
				`<div class="alert alert-danger">${__("Could not read the guide status.")}</div>`
			);
		});
}

function intro(status) {
	const declared = status.declared || 0;
	const summary = __("{0} pages are declared by the installed localisation apps.", [declared]);

	if (!status.wiki_installed) {
		return $(`
			<div class="alert alert-warning" role="alert">
				<b>${__("Frappe Wiki is not installed")}</b>
				<p class="mb-0">
					${summary}
					${__("Install Frappe Wiki to publish them on this site. The same content ships as Markdown in each app repository, which stays authoritative either way.")}
				</p>
			</div>
		`);
	}

	if (!status.can_publish) {
		return $(`
			<div class="alert alert-warning" role="alert">
				<b>${__("Read only")}</b>
				<p class="mb-0">
					${summary}
					${__("Publishing writes website content and needs the System Manager role, so this page shows the current state without offering to change it.")}
				</p>
			</div>
		`);
	}

	return $(`
		<div class="alert alert-info" role="alert">
			<p class="mb-0">
				${summary}
				${__("Publishing rewrites each page from the packaged Markdown and withdraws pages no installed app declares any more. Pages added by hand inside these spaces are left alone.")}
			</p>
		</div>
	`);
}

function contributors(status) {
	const rows = (status.contributors || [])
		.map(
			(row) => `
			<tr>
				<td>${frappe.utils.escape_html(row.app)}</td>
				<td class="text-right">${row.pages}</td>
			</tr>`
		)
		.join("");

	return $(`
		<h5>${__("Contributing apps")}</h5>
		<table class="table table-bordered">
			<thead>
				<tr><th>${__("App")}</th><th class="text-right">${__("Pages")}</th></tr>
			</thead>
			<tbody>${rows}</tbody>
		</table>
	`);
}

function spaces(status) {
	const rows = (status.spaces || [])
		.map((space) => {
			const link = space.exists
				? `<a href="/${space.route}" target="_blank">/${space.route}</a>`
				: `/${space.route}`;
			const state = !space.exists
				? `<span class="indicator-pill gray">${__("Not published")}</span>`
				: space.published === space.declared
					? `<span class="indicator-pill green">${__("Up to date")}</span>`
					: `<span class="indicator-pill orange">${__("Needs publishing")}</span>`;
			return `
				<tr>
					<td>${frappe.utils.escape_html(space.space_name)}</td>
					<td>${link}</td>
					<td class="text-right">${space.published} / ${space.declared}</td>
					<td>${state}</td>
				</tr>`;
		})
		.join("");

	return $(`
		<h5>${__("Guide spaces")}</h5>
		<table class="table table-bordered">
			<thead>
				<tr>
					<th>${__("Space")}</th>
					<th>${__("Route")}</th>
					<th class="text-right">${__("Published / Declared")}</th>
					<th>${__("Status")}</th>
				</tr>
			</thead>
			<tbody>${rows}</tbody>
		</table>
	`);
}

function publish(page, container) {
	frappe
		.call({ method: PUBLISH_METHOD, type: "POST" })
		.then((response) => {
			const result = response.message || {};
			frappe.show_alert({
				message: result.message || __("Publication queued."),
				indicator: result.indicator || "blue",
			});
			// The job runs on the long queue, so the counts only settle afterwards.
			setTimeout(() => render(page, container), 3000);
		});
}
