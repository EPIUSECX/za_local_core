from za_local_core.dashboards import repair_metric_presentation
from za_local_core.install import CORE_CHARTS, CORE_MODULE, CORE_NUMBER_CARDS
from za_local_core.sa_vat.install import VAT_CHARTS, VAT_MODULE, VAT_NUMBER_CARDS


def execute() -> None:
	"""Repair metrics created before the filter shape was corrected.

	The Desk reads a stored filter as ``[doctype, fieldname, operator, value]``, so
	the three-part filters shipped earlier made it report ``Invalid filter: =``.
	Currency cards also need full numbers, because Frappe renders a zero-valued
	one as ``R NaN``.
	"""
	repair_metric_presentation(CORE_MODULE, cards=CORE_NUMBER_CARDS, charts=CORE_CHARTS)
	repair_metric_presentation(VAT_MODULE, cards=VAT_NUMBER_CARDS, charts=VAT_CHARTS)
