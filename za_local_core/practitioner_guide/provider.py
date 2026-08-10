"""Core-owned pages for the federated localisation guides."""


def get_guide_sections() -> dict:
	return {
		"practitioner": [
			{
				"key": "getting-started",
				"title": "Getting Started",
				"order": 10,
				"pages": [
					{
						"slug": "start-here",
						"title": "Start Here: First-Run Setup",
						"file": "00_start_here.md",
					},
					{
						"slug": "overview",
						"title": "Overview and Capability Boundaries",
						"file": "01_overview.md",
					},
					{
						"slug": "installation",
						"title": "Installation and Migration",
						"file": "02_installation.md",
					},
					{
						"slug": "post-install-verification",
						"title": "Post-Install Verification",
						"file": "04_verification.md",
					},
				],
			},
			{
				"key": "foundation-setup-both-tracks",
				"title": "Foundation Setup",
				"order": 15,
				"pages": [
					{
						"slug": "company-registration",
						"title": "Company and Registration Details",
						"file": "10_company_registration.md",
					},
				],
			},
			{
				"key": "reference-operations",
				"title": "Governance, POPIA and Operations",
				"order": 80,
				"pages": [
					{
						"slug": "custom-fields-reference",
						"title": "Configuration Ownership",
						"file": "79_configuration_ownership.md",
					},
					{
						"slug": "statutory-source-governance",
						"title": "Statutory Source Governance",
						"file": "80_source_governance.md",
					},
					{
						"slug": "popia-paia-controls",
						"title": "POPIA and PAIA Controls",
						"file": "81_popia_paia.md",
					},
					{
						"slug": "troubleshooting-faq",
						"title": "Operations and Troubleshooting",
						"file": "82_operations.md",
					},
				],
			},
			{
				"key": "vat-finance",
				"title": "VAT and Finance",
				"order": 20,
				"pages": [
					{
						"slug": "vat-settings",
						"title": "South Africa VAT Settings",
						"file": "20_vat_settings.md",
					},
					{
						"slug": "tax-templates",
						"title": "Tax Templates and Classification",
						"file": "21_tax_templates.md",
					},
					{
						"slug": "tax-documents",
						"title": "Tax Invoices and Credit Notes",
						"file": "23_tax_documents.md",
					},
					{"slug": "vat201", "title": "VAT201 Working Paper", "file": "24_vat201.md"},
				],
			},
		],
		"user": [
			{
				"key": "getting-started",
				"title": "Getting Started",
				"order": 10,
				"pages": [
					{"slug": "welcome", "title": "Welcome and Responsibilities", "file": "u01_welcome.md"},
					{"slug": "workspaces", "title": "South African Workspaces", "file": "u02_workspaces.md"},
				],
			},
			{
				"key": "first-time-configuration",
				"title": "First-Time Configuration",
				"order": 15,
				"pages": [
					{"slug": "everyday-masters", "title": "Everyday Masters", "file": "u12_masters.md"},
				],
			},
			{
				"key": "reports",
				"title": "Reports",
				"order": 35,
				"pages": [
					{
						"slug": "finding-reports",
						"title": "Finding and Running Reports",
						"file": "u40_reports.md",
					},
					{
						"slug": "exporting-printing",
						"title": "Exporting and Printing",
						"file": "u44_exporting.md",
					},
				],
			},
			{
				"key": "working-with-vat",
				"title": "Working with VAT",
				"order": 20,
				"pages": [
					{
						"slug": "sales-and-purchases",
						"title": "Sales and Purchase VAT",
						"file": "u20_sales_purchases.md",
					},
					{"slug": "vat201-review", "title": "Prepare and Review VAT201", "file": "u23_vat201.md"},
				],
			},
		],
	}
