"""The guides tell practitioners where things live. That has to stay true."""

import re
from collections import defaultdict
from pathlib import Path

import frappe
from frappe.tests.classes import IntegrationTestCase

from za_local_core.practitioner_guide.registry import get_guides

# "SA Overview → Configuration → Statutory Sources"
NAV = re.compile(r"(SA (?:Overview|VAT|Payroll|Labour|COIDA))\s*→\s*([^→\n]+?)\s*→\s*([^→\n(]+)")


def _spoken(text: str) -> str:
	"""Strip markdown emphasis and any trailing ", or /desk/..." alternative."""
	return re.sub(r"[*_`]", "", text).split(",")[0].split(" or ")[0].strip().strip(".,;:")


class TestGuideNavigationMatchesTheDesk(IntegrationTestCase):
	def test_every_workspace_path_in_the_guides_resolves(self):
		"""A wrong card name sends a practitioner hunting through the Desk.

		Cheap to get wrong when a workspace is reorganised, and invisible until
		somebody follows the guide, so assert it against the real Workspace Links.
		"""
		rows = frappe.get_all(
			"Workspace Link",
			fields=["parent", "idx", "type", "label"],
			order_by="parent asc, idx asc",
			limit_page_length=0,
		)
		if not rows:
			self.skipTest("site has no workspace links")

		cards = defaultdict(list)
		items = defaultdict(set)
		current = {}
		for row in rows:
			if row.type == "Card Break":
				current[row.parent] = row.label
				cards[row.parent].append(row.label)
			else:
				items[(row.parent, current.get(row.parent))].add(row.label)

		failures = []
		for guide in get_guides():
			for group in guide["groups"]:
				for page in group["pages"]:
					path = Path(
						frappe.get_app_path(page["app"], "practitioner_guide", "content", page["file"])
					)
					for match in NAV.finditer(path.read_text(encoding="utf-8")):
						workspace = match.group(1)
						card = _spoken(match.group(2))
						item = _spoken(match.group(3))
						if not cards.get(workspace):
							continue  # that app is not installed on this bench
						if card not in cards[workspace]:
							failures.append(
								f"{path.name}: {workspace} has no card '{card}' "
								f"(cards: {', '.join(cards[workspace])})"
							)
						elif item not in items[(workspace, card)]:
							elsewhere = [c for c in cards[workspace] if item in items[(workspace, c)]]
							failures.append(
								f"{path.name}: {workspace} > {card} does not contain '{item}'"
								+ (f"; it is under '{elsewhere[0]}'" if elsewhere else "")
							)

		self.assertEqual([], failures, "guide navigation no longer matches the Desk:\n" + "\n".join(failures))
