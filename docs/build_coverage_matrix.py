"""Build docs/coverage-matrix.svg: the South African compliance coverage matrix.

Single source of truth for the matrix graphic. Edit ROWS, run this script, and copy the
SVG into docs/ of za_local_core, za_local_payroll and za_local_bma so all three match.

    python3 build_coverage_matrix.py coverage-matrix.svg

A cell is None (not included) or a short label. Labels: Preview, Manual (Controlled
Manual), Integration (Controlled Integration), Data, Extends, Uses, Report.
"""

from __future__ import annotations

import sys
from html import escape

PACKAGES = ("za_local_core", "za_local_payroll", "za_local_bma")

ROWS = [
	(
		"Payroll tax",
		[
			("PAYE: cumulative method, rebates, medical credits", None, "Preview", "Extends"),
			("UIF contributions", None, "Preview", "Preview"),
			("Skills Development Levy (SDL)", None, "Preview", None),
			("Employment Tax Incentive (ETI)", None, "Preview", None),
			("Retirement fund deductions and cap", None, "Preview", None),
			("Fringe benefits: company car, accommodation, loans", None, "Preview", None),
			("Tax directives, lump sums and severance tax", None, "Preview", "Extends"),
			("Travel allowance, subsistence and business trips", None, "Preview", None),
		],
	),
	(
		"Statutory returns",
		[
			("EMP201 monthly working paper", None, "Manual", "Extends"),
			("EMP501 reconciliation", None, "Manual", "Extends"),
			("IRP5 / IT3(a) certificates", None, "Manual", None),
			("VAT201 return", "Manual", None, None),
			("COIDA Return of Earnings", None, "Manual", None),
			("Skills development: WSP and ATR", None, "Manual", None),
			("Employment Equity working papers", None, "Manual", "Preview"),
		],
	),
	(
		"BCEA and labour",
		[
			("Annual leave: 12-month cycle, accrual, 6-month expiry", None, "Preview", None),
			("Sick leave: 36-month cycle, medical certificates", None, "Preview", None),
			("Family responsibility leave", None, "Preview", None),
			("Maternity, parental, adoption leave types", None, "Preview", None),
			("Notice, severance and leave payout on termination", None, "Preview", "Manual"),
			("Certificate of Service", None, None, "Manual"),
			("Sectoral minimum wages and bargaining councils", "Data", "Data", None),
			("Workplace injury and OID claims", None, "Preview", None),
		],
	),
	(
		"VAT and corporate",
		[
			("VAT registration and supply classification", "Preview", None, None),
			("Tax invoices, credit and debit notes", "Preview", None, None),
			("CIPC returns and beneficial ownership", "Manual", None, None),
		],
	),
	(
		"Payments, corrections and take-on",
		[
			("FNB Online Banking payment file", None, "Manual", None),
			("Other bank layouts and split pay", None, None, "Manual"),
			("Corrections, off-cycle runs and back pay", None, None, "Preview"),
			("Deduction orders: garnishees, maintenance, loans", None, None, "Preview"),
			("Mid-year take-on and parallel runs", None, None, "Manual"),
			("Leave liability, bonus accruals, cost allocation", None, None, "Preview"),
		],
	),
	(
		"Privacy, governance and people",
		[
			("Statutory sources and approved rate packs", "Manual", "Uses", None),
			("Filings, compliance calendar and receipts", "Manual", "Uses", None),
			("POPIA and PAIA registers", "Manual", "Uses", "Preview"),
			("SA ID, tax number and work-permit checks", None, None, "Preview"),
			("Recruitment and candidate portal", None, None, "Preview"),
			("Payroll readiness gate for new employees", None, "Preview", "Preview"),
			("Offboarding, clearance and access removal", None, None, "Manual"),
			("Sage 300 People handoff", None, None, "Integration"),
		],
	),
	(
		"Reports",
		[
			("Payroll and salary registers, department cost", None, "Report", None),
			("Income tax computation and deductions", None, "Report", None),
			("EMP201 report and statutory submissions summary", None, "Report", None),
			("Employment Equity workforce, movement, plan progress", None, "Report", "Report"),
			("VAT 201 linked transactions, classifications, audit", "Report", None, None),
			("Hiring funnel, cost per hire, onboarding compliance", None, None, "Report"),
			("Attrition, lifecycle timeline, payroll readiness", None, None, "Report"),
			("Variance review and year-end readiness", None, None, "Report"),
			("Feature readiness and compliance calendar", "Report", None, None),
		],
	),
	(
		"Not covered by any package",
		[
			("SARS eFiling, BRS and e@syFile submission", None, None, None),
			("eCOID and CF-2A transmission", None, None, None),
			("Certified Employment Equity forms and filing", None, None, None),
			("SETA portal submission and grant claims", None, None, None),
			("B-BBEE scoring", None, None, None),
			("Corporate and provisional tax returns", None, None, None),
			("Specialist VAT: mixed supplies, imports, customs, property", None, None, None),
			("UIF benefit claims", None, None, None),
			("Shared parental-leave pool tracking", None, None, None),
			("Collective agreements and hours-of-work rules", None, None, None),
		],
	),
]

NAVY, RED, H1, TEXT, MUTED, LINE, BAND = (
	"#1B2750",
	"#CE181E",
	"#24356A",
	"#333333",
	"#8A93A6",
	"#E3E6EC",
	"#F3F5F9",
)
GREEN = "#41AD49"
W, LABEL_X, COL_W = 1080, 28, 170
COL_X = [540 + i * (COL_W + 6) for i in range(3)]
ROW_H, SEC_H, HEAD_H = 30, 46, 92
FONT = "Verdana, 'DejaVu Sans', Arial, sans-serif"
HEAD_FONT = "'Century Gothic', Verdana, 'DejaVu Sans', sans-serif"


def tick(cx: float, cy: float, colour: str) -> str:
	return (
		f'<circle cx="{cx}" cy="{cy}" r="8" fill="{colour}"/>'
		f'<path d="M{cx - 3.6} {cy + 0.2} L{cx - 1} {cy + 2.8} L{cx + 4} {cy - 2.6}" '
		'fill="none" stroke="#fff" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>'
	)


def cross(cx: float, cy: float) -> str:
	return (
		f'<path d="M{cx - 4} {cy - 4} L{cx + 4} {cy + 4} M{cx + 4} {cy - 4} L{cx - 4} {cy + 4}" '
		f'stroke="#B8BECB" stroke-width="1.6" stroke-linecap="round" fill="none"/>'
	)


def build() -> str:
	total = HEAD_H + sum(SEC_H + len(rows) * ROW_H + 10 for _, rows in ROWS) + 96
	out = [
		f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{total}" viewBox="0 0 {W} {total}" '
		f'font-family="{FONT}" role="img" aria-label="South African compliance coverage matrix for the za_local packages">',
		f'<rect width="{W}" height="{total}" fill="#FFFFFF"/>',
		f'<rect width="{W}" height="6" fill="{RED}"/>',
		f'<text x="{LABEL_X}" y="46" font-family="{HEAD_FONT}" font-size="22" font-weight="700" fill="{H1}">South African compliance coverage</text>',
		f'<text x="{LABEL_X}" y="68" font-size="11" fill="{MUTED}">What each za_local package covers, how far, and what no package covers. Reviewed 8 October 2026.</text>',
	]
	y = HEAD_H
	for title, rows in ROWS:
		out.append(f'<rect x="0" y="{y}" width="{W}" height="{SEC_H - 10}" fill="{BAND}"/>')
		out.append(
			f'<text x="{LABEL_X}" y="{y + 21}" font-family="{HEAD_FONT}" font-size="14" font-weight="700" fill="{NAVY}">{escape(title)}</text>'
		)
		if title != ROWS[-1][0]:
			for x, name in zip(COL_X, PACKAGES, strict=True):
				out.append(
					f'<text x="{x + 8}" y="{y + 21}" font-size="10.5" font-weight="700" fill="{NAVY}">{name}</text>'
				)
		y += SEC_H
		for label, *cells in rows:
			cy = y + ROW_H / 2
			out.append(
				f'<text x="{LABEL_X}" y="{cy + 4}" font-size="11.5" fill="{TEXT}">{escape(label)}</text>'
			)
			for x, cell in zip(COL_X, cells, strict=True):
				if cell:
					colour = GREEN if cell == "Report" else NAVY
					out.append(tick(x + 16, cy, colour))
					out.append(
						f'<text x="{x + 32}" y="{cy + 4}" font-size="11" fill="{TEXT}">{escape(cell)}</text>'
					)
				else:
					out.append(cross(x + 16, cy))
			out.append(
				f'<line x1="{LABEL_X}" y1="{y + ROW_H}" x2="{W - LABEL_X}" y2="{y + ROW_H}" stroke="{LINE}" stroke-width="1"/>'
			)
			y += ROW_H
		y += 10
	lines = (
		"Preview: implemented and tested, practitioner sign-off needed.   Manual: prepared and approved in the app, filed or paid outside it.",
		"Integration: needs separate approval per client.   Data: reference records only.   Extends: adds controls to a feature another package owns.",
		"Uses: relies on the package that owns it.   Report: a report is included.   Cross: not included.",
		"No capability ships as Production. A status describes software readiness, not legal certification.",
	)
	for n, line in enumerate(lines):
		out.append(
			f'<text x="{LABEL_X}" y="{y + 22 + n * 16}" font-size="10" fill="{MUTED}">{escape(line)}</text>'
		)
	out.append("</svg>")
	return "\n".join(out)


if __name__ == "__main__":
	target = sys.argv[1] if len(sys.argv) > 1 else "coverage-matrix.svg"
	with open(target, "w") as handle:
		handle.write(build())
	print("wrote", target)
