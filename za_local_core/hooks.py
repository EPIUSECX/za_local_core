app_name = "za_local_core"
app_title = "SA Localisation"
app_publisher = "Cohenix"
app_description = (
	"South African VAT and compliance foundation: statutory sources, effective-dated "
	"rate packs, compliance profiles, filing controls, POPIA and PAIA registers, "
	"VAT201 working papers and compliant commercial documents for ERPNext."
)
app_email = "info@cohenix.com"
app_license = "mit"

za_local_practitioner_guide_provider = "za_local_core.practitioner_guide.provider.get_guide_sections"

# Apps
# ------------------

required_apps = ["frappe", "erpnext"]

after_install = "za_local_core.install.after_install"
after_migrate = "za_local_core.install.after_migrate"

scheduler_events = {
	"daily_long": ["za_local_core.tasks.daily"],
}

app_include_js = "/assets/za_local_core/js/za_local_feedback.js"

add_to_apps_screen = [
	{
		"name": "za_local_core",
		"title": "SA Localisation",
		"logo": "/assets/za_local_core/images/sa_map_icon.png",
		"route": "/desk/sa-overview",
		"has_permission": "za_local_core.api.has_app_permission",
	}
]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "za_local_core",
# 		"logo": "/assets/za_local_core/logo.png",
# 		"title": "SA Localisation Core",
# 		"route": "/za_local_core",
# 		"has_permission": "za_local_core.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/za_local_core/css/za_local_core.css"
# app_include_js = "/assets/za_local_core/js/za_local_core.js"

# include js, css files in header of web template
# web_include_css = "/assets/za_local_core/css/za_local_core.css"
# web_include_js = "/assets/za_local_core/js/za_local_core.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "za_local_core/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "za_local_core/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "za_local_core.utils.jinja_methods",
# 	"filters": "za_local_core.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "za_local_core.install.before_install"
# after_install = "za_local_core.install.after_install"

# Uninstallation
# ------------

before_uninstall = "za_local_core.install.before_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "za_local_core.utils.before_app_install"
# after_app_install = "za_local_core.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "za_local_core.utils.before_app_uninstall"
# after_app_uninstall = "za_local_core.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "za_local_core.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "za_local_core.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"za_local_core.tasks.all"
# 	],
# 	"daily": [
# 		"za_local_core.tasks.daily"
# 	],
# 	"hourly": [
# 		"za_local_core.tasks.hourly"
# 	],
# 	"weekly": [
# 		"za_local_core.tasks.weekly"
# 	],
# 	"monthly": [
# 		"za_local_core.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "za_local_core.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "za_local_core.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "za_local_core.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "za_local_core.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["za_local_core.utils.before_request"]
# after_request = ["za_local_core.utils.after_request"]

# Job Events
# ----------
# before_job = ["za_local_core.utils.before_job"]
# after_job = ["za_local_core.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"za_local_core.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# --- SA VAT ------------------------------------------------------------------
# Absorbed from za_local_finance, which is retired. The VAT module is inert until
# a company has South Africa VAT Settings, so a site that only runs payroll is
# unaffected by its presence.

doctype_js = {
	"Sales Invoice": "public/js/vat_tax_calculation.js",
	"Purchase Invoice": "public/js/vat_tax_calculation.js",
}

extend_doctype_class = {
	"Sales Invoice": "za_local_core.overrides.vat_invoices.ZASalesInvoice",
	"Purchase Invoice": "za_local_core.overrides.vat_invoices.ZAPurchaseInvoice",
}

doc_events = {
	"Customer": {
		"validate": "za_local_core.custom.customer.validate",
	},
	"Item": {
		"validate": "za_local_core.sa_vat.item_sync.sync_item_zero_rated_flag",
	},
	"ZA Submission Receipt": {
		"on_submit": "za_local_core.sa_vat.events.sync_vat201_from_receipt",
		"on_cancel": "za_local_core.sa_vat.events.sync_vat201_from_receipt",
	},
	"ZA Filing": {
		"on_cancel": "za_local_core.sa_vat.events.sync_vat201_from_filing",
	},
}

before_request = ["za_local_core.accounts.setup_chart.apply_chart_patches_on_request"]
