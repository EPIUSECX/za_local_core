from za_local_core.dashboards import repair_metric_presentation
from za_local_core.install import CORE_CHARTS, CORE_MODULE, CORE_NUMBER_CARDS
from za_local_core.sa_vat.install import VAT_CHARTS, VAT_MODULE, VAT_NUMBER_CARDS


def execute() -> None:
	"""Restamp metric currency from the site default.

	Number Card and Dashboard Chart persist a currency, and the metrics are seeded
	during app installation -- before the setup wizard has set the real one. They
	were therefore stamped with Frappe's shipped default and kept rendering South
	African statutory figures with a rupee symbol.
	"""
	repair_metric_presentation(CORE_MODULE, cards=CORE_NUMBER_CARDS, charts=CORE_CHARTS)
	repair_metric_presentation(VAT_MODULE, cards=VAT_NUMBER_CARDS, charts=VAT_CHARTS)
