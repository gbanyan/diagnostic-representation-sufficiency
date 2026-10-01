#!/usr/bin/env python3
"""Render the JBI manuscript figures from committed aggregate artifacts only.

Usage (from any directory):
    python3 figures/make_figures.py

Inputs: committed aggregate JSON/Markdown files under results/, exploratory/*/results/,
and docs/. No patient-level data are read. Every plotted number is read
programmatically from those files; only schematic labels are typed. Any count
below 10 (including zero) is displayed as "<10" or not displayed.

Outputs (in figures/): <name>.pdf (vector) and <name>.png (300 dpi) for
fig1_design, fig2_evidence, fig3_mcmed_pipeline, fig4_granularity,
figS1_calibration, figS2_attrition, plus figure_sources.json (source path and
keys per panel).
"""
import json
import re
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MM = 1 / 25.4
SINGLE_MM, DOUBLE_MM = 90, 190

# Okabe-Ito colorblind-safe palette; status is also encoded by marker shape.
BLUE = "#0072B2"      # confirmatory
VERM = "#D55E00"      # exploratory
GREEN = "#009E73"     # Model D+X series
GREY = "#6E6E6E"      # negative controls, reference lines
INK = "#1A1A1A"
MUTED = "#555555"
FILL_LIGHT = "#EEF4F9"
FILL_WARM = "#FBEFE6"
FILL_GREY = "#F2F2F2"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 7,
    "axes.labelsize": 7,
    "axes.titlesize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": INK,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "mathtext.fontset": "custom",
    "mathtext.rm": "Arial",
    "mathtext.it": "Arial:italic",
    "mathtext.bf": "Arial:bold",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "savefig.dpi": 300,
    "legend.frameon": False,
})

SOURCES = {}


def load(rel):
    return json.loads((ROOT / rel).read_text())


def note_src(fig, panel, rel, keys):
    SOURCES.setdefault(fig, {}).setdefault(panel, []).append({"path": rel, "keys": keys})


def count_txt(v):
    """Disclosure control: counts below 10 (including 0) are shown as '<10'."""
    if isinstance(v, (int, float)) and v >= 10:
        return f"{int(v):,}"
    return "<10"


def is_shown(v):
    return isinstance(v, (int, float)) and v >= 10


def num(x, nd):
    """Round half up on the decimal representation (0.2475 -> 0.248); unicode minus."""
    q = (x if isinstance(x, Decimal) else Decimal(repr(float(x)))).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)
    return f"{q:.{nd}f}".replace("-", "\u2212")


def pct(x, nd=1):
    return num(Decimal(repr(float(x))) * 100, nd)


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(HERE / f"{name}.{ext}", dpi=300)
    plt.close(fig)


def panel_letter(ax, letter, x=-0.02, y=1.0, fig=None):
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=9, fontweight="bold",
            va="bottom", ha="right")


# ---------------------------------------------------------------- schematic helpers
def box(ax, x, y, w, h, text="", fc="white", ec=INK, lw=0.7, fs=7, ha="center",
        va="center", weight="normal", ls="-", rounding=1.2, tc=INK, pad_x=1.5):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rounding}",
                       fc=fc, ec=ec, lw=lw, ls=ls)
    ax.add_patch(p)
    if text:
        tx = x + w / 2 if ha == "center" else x + pad_x
        ty = y + h / 2 if va == "center" else y + h - 1.2
        ax.text(tx, ty, text, ha=ha, va=va, fontsize=fs, fontweight=weight, color=tc,
                linespacing=1.25)
    return p


def arrow(ax, x0, y0, x1, y1, color=INK, lw=0.8, ls="-", style="-|>", ms=6, cs="arc3"):
    a = FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=ms,
                        color=color, lw=lw, ls=ls, connectionstyle=cs,
                        shrinkA=0, shrinkB=0)
    ax.add_patch(a)
    return a


def canvas(w_mm, h_mm):
    fig = plt.figure(figsize=(w_mm * MM, h_mm * MM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w_mm)
    ax.set_ylim(0, h_mm)
    ax.axis("off")
    return fig, ax


# ====================================================================== Figure 1
def fig1():
    name = "fig1_design"
    W, H = DOUBLE_MM, 96
    fig, ax = canvas(W, H)
    note_src(name, "all", "article Methods (not in this repository)",
             ["Sections 3.1, 3.4, 3.8, 3.10 (schematic labels only; no data values)"])
    XT = r"$X_t$"
    DH = r"$\hat{D}$"

    # Shared patient-state box
    box(ax, 38, 80, 56, 11, "Patient state " + XT + " at landmark T\n(only information available by T)",
        fc=FILL_WARM, ec=VERM, lw=0.8)

    # Column frames
    for x0, lab in ((4, "Model D"), (70, "Model D+X")):
        ax.add_patch(Rectangle((x0, 22), 58, 52, fc="none", ec="#BBBBBB", lw=0.5, ls=(0, (2, 2))))
    ax.text(6, 71.5, "Diagnostic model", fontsize=7, color=MUTED, va="top")
    ax.text(72, 71.5, "Diagnostic + patient-state model", fontsize=7, color=MUTED, va="top")

    # Inputs (left)
    box(ax, 8, 54, 24, 11, "D\ndiagnostic\nrepresentation", fc=FILL_LIGHT, ec=BLUE)
    box(ax, 35, 54, 24, 11, "C\ncommon context", fc=FILL_GREY, ec=GREY)
    # Inputs (right)
    box(ax, 73, 54, 17, 11, "D", fc=FILL_LIGHT, ec=BLUE)
    box(ax, 92, 54, 17, 11, "C", fc=FILL_GREY, ec=GREY)
    box(ax, 111, 54, 17, 11, XT, fc=FILL_WARM, ec=VERM)
    arrow(ax, 94, 80, 119.5, 65.3, color=VERM)

    # Models
    box(ax, 13, 38, 40, 10, "Model D\nlogistic; D, C unpenalized", weight="normal")
    box(ax, 79, 38, 43, 10, "Model D+X\nadds L2-penalized " + XT + " (additive)")
    for x in (20, 47):
        arrow(ax, x, 54, x if x < 30 else x - 4, 48.2)
    for x, xe in ((81.5, 88), (100.5, 100.5), (119.5, 113)):
        arrow(ax, x, 54, xe, 48.2)

    # Outputs
    box(ax, 13, 25, 40, 8.5, "Predicted Y; held-out log loss " + r"$L_D$", fc="white")
    box(ax, 79, 25, 43, 8.5, "Predicted Y; held-out log loss " + r"$L_{DX}$", fc="white")
    arrow(ax, 33, 38, 33, 33.7)
    arrow(ax, 100.5, 38, 100.5, 33.7)

    # Shaded bracket for Delta L
    ax.add_patch(Rectangle((33, 8), 67.5, 12.5, fc="#DCE9F3", ec="none", alpha=0.9))
    ax.plot([33, 33, 100.5, 100.5], [25, 20.5, 20.5, 25], color=BLUE, lw=0.9)
    ax.text(66.75, 17.6, r"$\Delta L$ (held-out log-loss reduction) $= L_D - L_{DX}$",
            ha="center", va="center", fontsize=8, fontweight="bold", color=INK)
    ax.text(66.75, 11.8, r"$\Delta$bits $= \Delta L/\ln 2$     fractional reduction $= \Delta L/L_D$",
            ha="center", va="center", fontsize=7)
    ax.text(66.75, 3.6,
            "Sufficiency rejected only if the 95% CI of " + r"$\Delta L$" + " excludes 0 and "
            + r"$\Delta L/L_D \geq$" + " 10%\n(prespecified margin, fractional scale only)",
            ha="center", va="center", fontsize=7, color=MUTED)

    # Inset: how D is obtained in each cohort
    ix, iw = 133, 54
    ax.add_patch(Rectangle((ix, 4), iw, 87, fc="#FAFAFA", ec="#999999", lw=0.6))
    ax.text(ix + 2, 88.5, "How D is obtained", fontsize=7.5, fontweight="bold", va="top")

    # MIMIC sub-panel
    ax.text(ix + 2, 82, "MIMIC-IV (landmark T = 6 h)", fontsize=7, fontweight="bold",
            va="top", color=BLUE)
    # mini timeline
    ty = 72
    ax.plot([ix + 4, ix + iw - 4], [ty, ty], color=INK, lw=0.6)
    for xx, lab in ((ix + 5, "ED\narrival"), (ix + 21, "T"), (ix + iw - 6, "discharge")):
        ax.plot([xx, xx], [ty - 1, ty + 1], color=INK, lw=0.6)
        ax.text(xx, ty - 2, lab, ha="center", va="top", fontsize=7)
    box(ax, ix + 4, 52, iw - 8, 10.5,
        "D = observed discharge diagnosis\n(4 classes), assigned after the\nencounter; an input, not built from " + XT,
        fc=FILL_LIGHT, ec=BLUE, fs=7)
    arrow(ax, ix + iw - 6, ty - 5.2, ix + iw - 6, 62.7, color=BLUE, cs="arc3")

    ax.plot([ix + 3, ix + iw - 3], [48.5, 48.5], color="#BBBBBB", lw=0.5)

    # MC-MED sub-panel
    ax.text(ix + 2, 46, "MC-MED (landmark T = 3 h)", fontsize=7, fontweight="bold",
            va="top", color=BLUE)
    box(ax, ix + 4, 33.5, 14, 7.5, XT, fc=FILL_WARM, ec=VERM)
    box(ax, ix + 23, 31.5, iw - 27, 11.5, "cross-fitted encoder\n(5-fold, patient-\ngrouped)",
        fc="white", ec=INK, fs=7)
    arrow(ax, ix + 18, 37.25, ix + 23, 37.25)
    box(ax, ix + 4, 8, iw - 8, 15.5,
        DH + " = soft 20-class posterior\n(19 columns), used as D in both\nmodels; generated from the\nsame " + XT,
        fc=FILL_LIGHT, ec=BLUE, fs=7)
    arrow(ax, ix + 37, 31.5, ix + 30, 23.7)
    ax.text(ix + iw - 2, 27.6, "supervised by\nvisit diagnosis", ha="right", va="center",
            fontsize=7, color=MUTED)

    save(fig, name)


# ====================================================================== Figure 2
def fig2():
    name = "fig2_evidence"
    base = "results/main/target_sufficiency/"
    rows = []

    def mimic(code, file, title, status, endpoint):
        rel = base + file
        d = load(rel)
        rep0 = d["repeats"][0]
        ci = rep0["bootstrap_ci"]
        m = rep0["metrics"]
        ar = d["across_repeats"]
        note_src(name, f"row {code}", rel,
                 ["across_repeats.rel_delta.mean", "across_repeats.delta.mean (bits)",
                  "repeats[0].bootstrap_ci.rel_delta", "repeats[0].bootstrap_ci.delta",
                  "repeats[0].metrics.n", "repeats[0].metrics.events"])
        ev = m.get("events")
        ntxt = f"n = {count_txt(m['n'])}" + (f"; {count_txt(ev)} events" if ev is not None else "; multiclass")
        rows.append(dict(title=title, status=status, endpoint=endpoint, ntxt=ntxt,
                         rel=ar["rel_delta"]["mean"], rel_lo=ci["rel_delta"][0], rel_hi=ci["rel_delta"][1],
                         db=ar["delta"]["mean"], db_lo=ci["delta"][0], db_hi=ci["delta"][1]))

    mimic("T1", "primary_T1.json", "Index procedural intervention", "confirmatory",
          "index procedure after the 6 h landmark")
    mimic("T3", "secondary_T3.json", "Later ICU transfer", "exploratory",
          "first ICU entry after the 6 h landmark")
    mimic("M5", "control_M5.json", "Anaerobic coverage", "negative control",
          "anaerobic coverage of antibiotic orders, 24 h")
    mimic("T5", "control_T5.json", "Organ operated on", "negative control",
          "organ operated on during the admission")
    mimic("M3", "control_M3.json", "Anticoagulant choice", "negative control",
          "enoxaparin vs SC heparin, 48 h")

    rel = "results/mcmed/stageG_test_primary.json"
    g = load(rel)
    s, b = g["summary"], g["bootstrap_95ci"]
    note_src(name, "row MC-MED", rel,
             ["summary.relative_gain", "summary.delta_bits", "bootstrap_95ci.relative_gain",
              "bootstrap_95ci.delta_bits", "summary.n", "summary.events"])
    rows.append(dict(title="ED-to-ICU disposition", status="confirmatory",
                     endpoint="admitted visits undecided at 3 h; locked test",
                     ntxt=f"n = {count_txt(s['n'])}; {count_txt(s['events'])} events",
                     rel=s["relative_gain"], rel_lo=b["relative_gain"]["lo"], rel_hi=b["relative_gain"]["hi"],
                     db=s["delta_bits"], db_lo=b["delta_bits"]["lo"], db_hi=b["delta_bits"]["hi"]))

    style = {
        "confirmatory": dict(marker="o", mfc=BLUE, mec=BLUE, color=BLUE, ms=5),
        "exploratory": dict(marker="D", mfc=VERM, mec=VERM, color=VERM, ms=4.2),
        "negative control": dict(marker="s", mfc="white", mec=GREY, color=GREY, ms=4.2),
    }
    # y layout: group header rows interleaved
    layout = [("MIMIC-IV (repeated nested cross-validation)", None)] + \
             [(None, rows[i]) for i in range(5)] + \
             [("MC-MED (locked test set)", None), (None, rows[5])]
    ys, y = [], 0.0
    for hdr, r in layout:
        ys.append(y)
        y -= 0.8 if hdr else 1.0
    ymin = y + 0.4

    W, H = DOUBLE_MM, 100
    fig = plt.figure(figsize=(W * MM, H * MM))
    top, bot = 0.90, 0.17
    axL = fig.add_axes([0.005, bot, 0.27, top - bot])
    axF = fig.add_axes([0.30, bot, 0.27, top - bot])
    axB = fig.add_axes([0.61, bot, 0.17, top - bot])
    axV = fig.add_axes([0.80, bot, 0.195, top - bot])
    for a in (axL, axF, axB, axV):
        a.set_ylim(ymin, 0.6)
    for a in (axL, axV):
        a.axis("off")
        a.set_xlim(0, 1)

    axV.text(0.0, 0.55, "Fractional, % (95% CI)\n" + r"$\Delta$bits (95% CI)", fontsize=7,
             fontweight="bold", va="bottom")
    for (hdr, r), yy in zip(layout, ys):
        if hdr:
            axL.text(0.0, yy, hdr, fontsize=7, fontweight="bold", va="center")
            continue
        axL.text(0.03, yy + 0.28, f"{r['title']} ({r['status']})", fontsize=7, va="center")
        axL.text(0.03, yy - 0.02, r["endpoint"], fontsize=7, va="center", color=MUTED)
        axL.text(0.03, yy - 0.32, r["ntxt"], fontsize=7, va="center", color=MUTED)
        st = style[r["status"]]
        for a, (p, lo, hi, k) in ((axF, (r["rel"], r["rel_lo"], r["rel_hi"], 100)),
                                  (axB, (r["db"], r["db_lo"], r["db_hi"], 1))):
            a.plot([lo * k, hi * k], [yy, yy], color=st["color"], lw=1.1, solid_capstyle="butt")
            a.plot([p * k], [yy], ls="none", marker=st["marker"], ms=st["ms"], mfc=st["mfc"],
                   mec=st["mec"], mew=0.9, zorder=3)
        axV.text(0.0, yy + 0.15, f"{pct(r['rel'])} ({pct(r['rel_lo'])} to {pct(r['rel_hi'])})",
                 fontsize=7, va="center")
        axV.text(0.0, yy - 0.17, f"{num(r['db'], 3)} ({num(r['db_lo'], 3)} to {num(r['db_hi'], 3)})",
                 fontsize=7, va="center", color=MUTED)
    for yy, (hdr, r) in zip(ys, layout):
        if hdr:
            for a in (axF, axB):
                a.axhline(yy, color="#DDDDDD", lw=0.5)

    for a in (axF, axB):
        a.set_yticks([])
        a.spines["left"].set_visible(False)
        a.axvline(0, color=GREY, lw=0.6)
    axF.set_xlim(-5, 25)
    axF.set_xticks([-5, 0, 5, 10, 15, 20, 25])
    axF.set_xlabel(r"Fractional log-loss reduction, $\Delta L/L_D$ (%)")
    # Margin drawn only through the confirmatory rows: it was prespecified for those analyses alone.
    for (hdr, r), yy in zip(layout, ys):
        if not hdr and r["status"] == "confirmatory":
            axF.plot([10, 10], [yy - 0.45, yy + 0.45], color=INK, lw=0.8, ls=(0, (3, 1.5)))
    axF.text(10.4, 0.55, "prespecified 10% margin\n(confirmatory analyses only)", fontsize=7, va="bottom", ha="left")
    axB.set_xlim(-0.01, 0.06)
    axB.set_xticks([0, 0.02, 0.04, 0.06])
    axB.set_xticklabels(["0", "0.02", "0.04", "0.06"])
    axB.set_xlabel(r"$\Delta$bits per observation")
    panel_letter(axF, "A", x=0.0, y=1.045)
    panel_letter(axB, "B", x=0.0, y=1.045)

    handles = [Line2D([], [], ls="-", lw=1.1, color=v["color"], marker=v["marker"], ms=v["ms"],
                      mfc=v["mfc"], mec=v["mec"], label=k) for k, v in style.items()]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.30, 0.0), ncol=3,
               handlelength=2.2, columnspacing=2.0)
    fig.text(0.005, 0.01, "No pooled estimate. MIMIC-IV: point = mean of\n3 repeats; CI = 2,000-replicate "
             "bootstrap of\nrepeat 1. MC-MED: 2,000-replicate patient-\ncluster bootstrap of the locked test set.",
             fontsize=7, color=MUTED, va="bottom")
    save(fig, name)


# ====================================================================== Figure 3
def parse_audit_trail(rel):
    """Return {row number: dict(date, time, event, commit)} from the Markdown timeline table."""
    out, cur_date = {}, None
    for line in (ROOT / rel).read_text().splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|(.*)$", line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        tcell = cells[0].replace("*", "")
        dm = re.search(r"(\d{4}-\d{2}-\d{2})", tcell)
        if dm:
            cur_date = dm.group(1)
        tm = re.search(r"(\d{2}:\d{2}(?::\d{2})?)", tcell)
        out[int(m.group(1))] = dict(date=cur_date, time=tm.group(1) if tm else None,
                                    event=cells[1].replace("*", ""), commit=cells[2].replace("*", ""))
    return out


def fig3():
    name = "fig3_mcmed_pipeline"
    rc = "results/mcmed/stageA_cohort.json"
    rs = "results/mcmed/stageC_split.json"
    re_ = "results/mcmed/stageE_encoder_body_primary.json"
    rf = "results/mcmed/stageF_develop_primary.json"
    rg = "results/mcmed/stageG_test_primary.json"
    rt = "docs/confirmatory_audit_trail.md"
    coh, spl, enc, dev, tst = load(rc), load(rs), load(re_), load(rf), load(rg)
    trail = parse_audit_trail(rt)
    att = {a["step"]: a for a in coh["attrition"]}
    note_src(name, "box 1 cohort", rc, ["attrition[*].visits", "attrition[*].excluded.visits",
                                         "final.visits", "final.patients", "final.icu"])
    note_src(name, "box 2 X_3h", rf, ["X_raw_columns", "X_model_columns_after_indicators"])
    note_src(name, "box 3 split", rs, ["by_set.dev", "by_set.test", "patient_overlap", "test_fraction"])
    note_src(name, "box 4 encoder + gate", re_, ["n_classes", "dev_oof.relative_reduction_vs_prior",
                                                  "dev_oof.per_fold", "dev_oof.top1_accuracy",
                                                  "dev_oof.majority_class_share", "adequacy_rule", "adequate"])
    note_src(name, "box 4 encoder + gate", rf, ["D_block_columns"])
    note_src(name, "box 5 dev tuning", rf, ["inner_cv_mean_logloss_DX_by_C (grid size)", "C_selected", "solver"])
    note_src(name, "box 6 test", rg, ["summary.n", "summary.events", "summary.relative_gain",
                                       "bootstrap_95ci.relative_gain", "bootstrap_95ci.delta_bits.reps"])
    note_src(name, "timeline", rt, ["Timeline rows 15, 19, 22, 23 (Time, Event, Commit / tag)"])

    W, H = DOUBLE_MM, 140
    fig, ax = canvas(W, H)

    admitted = att["admitted (Inpatient/Observation/ICU)"]
    ex = {a["step"]: a.get("excluded", {}).get("visits") for a in coh["attrition"]}
    ex_dispo = ex["Dispo_time > T"]
    ex_order = ex["decision_time = min(Dispo_time, first ADT order) > T"]
    ex_consult = ex["no ICU / critical-care consult at or before T"]
    ex_unmapped = ex["primary CCSR mapping available (unmapped excluded)"]
    ex_other = ex["valid Arrival_time and Dispo_time"] + ex["age >= 18"]
    fin = coh["final"]

    # Box 1: cohort
    y1, h1 = 115, 22
    box(ax, 3, y1, 60, h1,
        "1  Cohort and landmark (T = arrival + 3 h)\n"
        f"{count_txt(admitted['visits'])} admitted adult visits\n"
        "decision time = earlier of disposition and\nfirst admission or transfer order;\n"
        "consult exclusion; CCSR v2024.1 mapping",
        ha="left", va="top", fc="white")
    box(ax, 68, y1, 58, h1,
        "Excluded\n"
        f"disposition documented by T: {count_txt(ex_dispo)}\n"
        f"admission or transfer order by T: {count_txt(ex_order)}\n"
        f"ICU or critical-care consult by T: {count_txt(ex_consult)}\n"
        f"no CCSR mapping: {count_txt(ex_unmapped)}\n"
        f"invalid times or age < 18: {count_txt(ex_other)}",
        ha="left", va="top", fc=FILL_GREY, ec=GREY)
    arrow(ax, 63, y1 + h1 / 2, 68, y1 + h1 / 2)
    box(ax, 131, y1 + 1, 56, h1 - 2,
        f"Analysis cohort\n{count_txt(fin['visits'])} visits\n"
        f"({count_txt(fin['patients'])} patients)\n"
        f"ICU disposition {count_txt(fin['icu']['n'])} ({fin['icu']['pct']:.1f}%)",
        fc=FILL_LIGHT, ec=BLUE)
    arrow(ax, 126, y1 + h1 / 2, 131, y1 + h1 / 2)

    # Box 2: X_3h
    y2 = 100
    box(ax, 131, y2, 56, 11,
        "2  " + r"$X_{3h}$" + f" built by result-time rule\n{dev['X_raw_columns']} variables "
        f"({dev['X_model_columns_after_indicators']} columns)", fc="white")
    arrow(ax, 159, y1 + 1, 159, y2 + 11)

    # Box 3: split
    y3 = 87
    tf = spl["test_fraction"]
    box(ax, 131, y3, 56, 9,
        f"3  Salted hash split by patient\n{int(round(100 * (1 - tf)))}/{int(round(100 * tf))}; "
        f"patient overlap {spl['patient_overlap']}", fc="white")
    arrow(ax, 159, y2, 159, y3 + 9)

    dv, ts = spl["by_set"]["dev"], spl["by_set"]["test"]
    yb = 72
    box(ax, 3, yb, 60, 10,
        f"Development: {count_txt(dv['visits'])} visits\n"
        f"({count_txt(dv['patients'])} patients; {count_txt(dv['icu']['n'])} ICU, {dv['icu']['pct']:.1f}%)",
        fc=FILL_LIGHT, ec=BLUE)
    box(ax, 131, yb, 56, 10,
        f"Locked test: {count_txt(ts['visits'])} visits\n"
        f"({count_txt(ts['patients'])} patients; {count_txt(ts['icu']['n'])} ICU, {ts['icu']['pct']:.1f}%)",
        fc=FILL_WARM, ec=VERM)
    arrow(ax, 140, y3, 33, yb + 10)
    arrow(ax, 168, y3, 168, yb + 10)

    # Box 4: encoder + gate
    folds = enc["dev_oof"]["per_fold"]
    n_better = sum(1 for f in folds if f["logloss"] < f["prior_logloss"])
    rule = enc["adequacy_rule"]
    y4, h4 = 49, 18
    box(ax, 3, y4, 60, h4,
        f"4  {len(folds)}-fold patient-grouped cross-fitted\nencoder (diagnosis label only)\n"
        "→ soft " + r"$\hat{D}$" + f", {enc['n_classes']} classes ({dev['D_block_columns']} columns)\n"
        "test " + r"$\hat{D}$" + ": encoder fitted on all\ndevelopment patients",
        ha="left", va="top", fc="white")
    arrow(ax, 33, yb, 33, y4 + h4)
    gate_ok = "passed" if enc["adequate"] else "FAILED"
    box(ax, 68, y4, 58, h4,
        f"Encoder adequacy gate: {gate_ok}\n"
        f"OOF log loss {pct(enc['dev_oof']['relative_reduction_vs_prior'])}% below prior "
        f"(≥ {int(100 * rule['min_relative_logloss_reduction_vs_prior'])}% required)\n"
        f"lower than prior in {n_better} of {len(folds)} folds\n"
        f"top-1 accuracy {num(enc['dev_oof']['top1_accuracy'], 3)} vs majority-class\n"
        f"share {num(enc['dev_oof']['majority_class_share'], 3)}",
        ha="left", va="top", fc=FILL_GREY, ec=GREY)
    ax.plot([63, 68], [y4 + h4 / 2] * 2, color=INK, lw=0.8, ls=(0, (2, 1.5)))

    # Box 5: dev tuning
    y5, h5 = 29, 13
    ngrid = len(dev["inner_cv_mean_logloss_DX_by_C"])
    box(ax, 3, y5, 60, h5,
        f"5  Development tuning of Model D+X\nL2 penalty from {ngrid} values by inner CV\n"
        f"(selected C = {dev['C_selected']}); exact Newton solver",
        ha="left", va="top", fc="white")
    arrow(ax, 33, y4, 33, y5 + h5)

    # Box 6: test evaluation
    y6, h6 = 31.5, 35.5
    reps = tst["bootstrap_95ci"]["relative_gain"]["reps"]
    box(ax, 131, y6, 56, h6 - 2,
        "6  Single locked-test evaluation\nModels D and D+X fitted on\ndevelopment, evaluated once\n"
        f"({reps:,}-replicate patient-cluster\nbootstrap)\n"
        r"$\Delta L/L_D$" + f" = {pct(tst['summary']['relative_gain'])}% "
        f"({pct(tst['bootstrap_95ci']['relative_gain']['lo'])} to "
        f"{pct(tst['bootstrap_95ci']['relative_gain']['hi'])})",
        ha="left", va="top", fc=FILL_WARM, ec=VERM)
    arrow(ax, 159, yb, 159, y6 + h6 - 2)
    # test D_hat path (dashed), routed below the gate box
    ax.plot([55, 55, 128], [y4, y4 - 3, y4 - 3], color=MUTED, lw=0.8, ls=(0, (3, 2)))
    arrow(ax, 128, y4 - 3, 131, y4 - 3, color=MUTED)
    ax.text(97, y4 - 3.6, "test " + r"$\hat{D}$" + " from encoder fitted on development",
            ha="center", va="top", fontsize=7, color=MUTED)
    arrow(ax, 63, y5 + 5, 131, y5 + 5)
    ax.text(97, y5 + 5.6, "frozen Models D and D+X", ha="center", va="bottom", fontsize=7, color=MUTED)

    # Timeline strip with a broken axis (two time windows on 2026-10-01)
    want = {15: "Protocol tag", 19: "Amendment 1 (before test opening)", 22: "Locked test opened",
            23: "Primary-result tag"}
    evs = []
    for k, lab in want.items():
        r = trail[k]
        t = datetime.strptime(f"{r['date']} {r['time']}", "%Y-%m-%d %H:%M:%S")
        code = re.findall(r"`([^`]+)`", r["commit"])
        evs.append((t, lab, r["time"], code))
    t_first, t_last = evs[0][0], evs[-1][0]
    seg1 = (t_first.replace(minute=20, second=0), t_first.replace(minute=50, second=0), 22.0, 72.0)
    seg2_start = evs[1][0].replace(second=0) - timedelta(minutes=1)
    seg2 = (seg2_start, t_last.replace(second=0) + timedelta(minutes=1), 92.0, 184.0)
    ty = 9.0

    def X(t):
        for a0, a1, xa, xb in (seg1, seg2):
            if a0 <= t <= a1:
                return xa + (xb - xa) * (t - a0).total_seconds() / (a1 - a0).total_seconds()
        raise ValueError(t)

    for (a0, a1, xa, xb), step in ((seg1, 10), (seg2, 1)):
        ax.plot([xa, xb], [ty, ty], color=INK, lw=0.7)
        tk = a0
        while tk <= a1:
            ax.plot([X(tk)] * 2, [ty - 0.8, ty], color=INK, lw=0.5)
            ax.text(X(tk), ty - 1.3, tk.strftime("%H:%M"), ha="center", va="top", fontsize=7, color=MUTED)
            tk += timedelta(minutes=step)
    for xx in (seg1[3] + 8, seg1[3] + 9.2):
        ax.plot([xx - 0.6, xx + 0.6], [ty - 1.2, ty + 1.2], color=INK, lw=0.7)
    ax.plot([seg1[3], seg1[3] + 8], [ty, ty], color=INK, lw=0.7, ls=(0, (1, 1.5)))
    ax.plot([seg1[3] + 9.2, seg2[2]], [ty, ty], color=INK, lw=0.7, ls=(0, (1, 1.5)))
    ax.text(3, ty, t_first.strftime("%Y-%m-%d") + "\n(UTC+8)", ha="left", va="center", fontsize=7)
    # label anchor (x, height above axis, ha)
    place = [(None, 3.5, "center"), (None, 3.5, "center"), (None, 3.5, "center"), (None, 11.5, "center")]
    for i, (t, lab, tstr, code) in enumerate(evs):
        x = X(t)
        col = VERM if i >= 2 else BLUE
        ax.plot([x], [ty], marker="o" if i == 0 else "v", color=col, ms=4.5, zorder=3)
        tag = [c for c in code if not re.fullmatch(r"[0-9a-f]{7}", c)]
        extra = f"\n{tag[0]}" if tag else (f"\ncommit {code[0]}" if code else "")
        lx = x if place[i][0] is None else place[i][0]
        if i == 3:
            lx = x + 4
            place[i] = (None, 11.5, "right")
        h = place[i][1]
        ax.plot([x, lx], [ty + 0.8, ty + h - 0.4], color=MUTED, lw=0.5)
        ax.text(lx, ty + h, f"{lab}\n{tstr}{extra}", ha=place[i][2], va="bottom", fontsize=7)
    save(fig, name)


# ====================================================================== Figure 4
def fig4():
    name = "fig4_granularity"
    rc = "exploratory/diagnostic_capacity/results/capacity.json"
    rp = "exploratory/diagnostic_capacity/results/capacity_paired_diff.json"
    rg = "results/mcmed/stageG_test_primary.json"
    cap, pdif, g = load(rc)["ontologies"], load(rp), load(rg)
    ccsr = ["R2_ccsr_body_system", "R3_ccsr_category_min300", "R4_ccsr_category_min100", "R5_ccsr_category_min50"]
    icd = ["R1_icd10_chapter", "R6_icd10_3char_min100", "R7_icd10_3char_min50"]
    note_src(name, "A (upper): fractional reduction, CCSR", rc,
             [f"ontologies.{k}.n_classes / soft_dhat.relative_gain / soft_dhat.ci95.relative_gain" for k in ccsr[1:]]
             + [f"ontologies.{k}.hindsight_label_reference.relative_gain/ci95" for k in ("R2_ccsr_body_system", "R5_ccsr_category_min50")])
    note_src(name, "A (upper): fractional reduction, CCSR", rg,
             ["20-class confirmatory point: summary.relative_gain, bootstrap_95ci.relative_gain (2,000 reps)"])
    note_src(name, "A (lower): paired difference vs 20 classes", rp,
             [f"differences.{k}_minus_R2_ccsr_body_system.rel" for k in ccsr[1:]])
    note_src(name, "B: log loss", rp, [f"points.{k}.LD / LDX" for k in ccsr])
    note_src(name, "C: ICD-10 points", rc,
             [f"ontologies.{k}.soft_dhat.relative_gain/ci95" for k in icd]
             + ["ontologies.R7_icd10_3char_min50.hindsight_label_reference.relative_gain/ci95"])

    W, H = DOUBLE_MM, 82
    fig = plt.figure(figsize=(W * MM, H * MM))
    L, B0, Hh = 0.085, 0.25, 0.68
    axA = fig.add_axes([L, B0 + 0.30, 0.25, Hh - 0.30])
    axA2 = fig.add_axes([L, B0, 0.25, 0.24], sharex=axA)
    axB = fig.add_axes([0.41, B0, 0.24, Hh])
    axC = fig.add_axes([0.745, B0, 0.24, Hh])

    def ci_pt(ax, x, p, lo, hi, color, marker, mfc, ms=4.5, z=3):
        ax.plot([x, x], [lo, hi], color=color, lw=1.0, zorder=z - 1)
        ax.plot([x], [p], ls="none", marker=marker, ms=ms, mfc=mfc, mec=color, mew=0.9, zorder=z)

    # Panel A upper
    xs = [cap[k]["n_classes"] for k in ccsr]
    s, bci = g["summary"], g["bootstrap_95ci"]["relative_gain"]
    ci_pt(axA, xs[0], 100 * s["relative_gain"], 100 * bci["lo"], 100 * bci["hi"], BLUE, "o", BLUE, ms=5.5)
    for k, x in zip(ccsr[1:], xs[1:]):
        sd = cap[k]["soft_dhat"]
        ci_pt(axA, x, 100 * sd["relative_gain"], 100 * sd["ci95"]["relative_gain"]["lo"],
              100 * sd["ci95"]["relative_gain"]["hi"], VERM, "D", VERM)
    for k in ("R2_ccsr_body_system", "R5_ccsr_category_min50"):
        h = cap[k]["hindsight_label_reference"]
        x = cap[k]["n_classes"] * 1.10
        ci_pt(axA, x, 100 * h["relative_gain"], 100 * h["ci95"]["relative_gain"]["lo"],
              100 * h["ci95"]["relative_gain"]["hi"], INK, "o", "white")
    axA.annotate("confirmatory", xy=(xs[0], 100 * s["relative_gain"]), xytext=(xs[0] * 0.98, 6.5),
                 fontsize=7, color=BLUE, ha="left",
                 arrowprops=dict(arrowstyle="-", color=BLUE, lw=0.5))
    axA.text(30, 29.5, "hollow: actual visit diagnosis\n(post-decision)", fontsize=7, va="top", ha="left")
    axA.set_ylabel(r"$\Delta L/L_D$ (%)")
    axA.set_ylim(0, 30)
    axA.set_yticks([0, 10, 20, 30])
    plt.setp(axA.get_xticklabels(), visible=False)
    panel_letter(axA, "A", x=-0.17, y=1.0)

    # Panel A lower: paired differences
    axA2.axhline(0, color=GREY, lw=0.6)
    axA2.plot([xs[0]], [0], ls="none", marker="o", ms=4, mfc=BLUE, mec=BLUE)
    axA2.text(xs[0] * 1.08, 0.6, "reference", fontsize=7, color=MUTED, va="bottom")
    for k, x in zip(ccsr[1:], xs[1:]):
        r = pdif["differences"][f"{k}_minus_R2_ccsr_body_system"]["rel"]
        ci_pt(axA2, x, 100 * r["point"], 100 * r["lo"], 100 * r["hi"], VERM, "D", VERM)
    axA2.set_ylim(-14, 3)
    axA2.set_yticks([-12, -8, -4, 0])
    axA2.set_ylabel("Diff. vs 20\nclasses (pp)")

    for a in (axA, axA2, axB, axC):
        a.set_xscale("log")
        a.minorticks_off()
    for a in (axA2, axB):
        a.set_xlim(16, 160)
        a.set_xticks(xs)
        a.set_xticklabels([str(x) for x in xs])
        a.set_xlabel("Diagnostic classes (CCSR, log scale)")

    # Panel B: log loss
    pts = pdif["points"]
    LD = [pts[k]["LD"] for k in ccsr]
    LDX = [pts[k]["LDX"] for k in ccsr]
    axB.plot(xs, LD, ls="none", marker="o", ms=4.5, mfc=INK, mec=INK)
    axB.plot(xs, LDX, ls="none", marker="^", ms=5, mfc=GREEN, mec=GREEN)
    axB.text(xs[-1] * 1.13, LD[-1], "Model D", fontsize=7, va="center", ha="left")
    axB.text(xs[-1] * 1.13, LDX[-1], "Model D+X", fontsize=7, va="center", ha="left", color=INK)
    axB.set_xlim(16, 230)
    axB.set_ylim(0.14, 0.19)
    axB.set_ylabel("Held-out log loss (bits per visit)")
    panel_letter(axB, "B", x=-0.2, y=1.0)

    # Panel C: ICD-10 points and hindsight
    xi = [cap[k]["n_classes"] for k in icd]
    for k, x in zip(icd, xi):
        sd = cap[k]["soft_dhat"]
        ci_pt(axC, x, 100 * sd["relative_gain"], 100 * sd["ci95"]["relative_gain"]["lo"],
              100 * sd["ci95"]["relative_gain"]["hi"], VERM, "s", VERM)
    h = cap["R7_icd10_3char_min50"]["hindsight_label_reference"]
    ci_pt(axC, xi[-1] * 1.10, 100 * h["relative_gain"], 100 * h["ci95"]["relative_gain"]["lo"],
          100 * h["ci95"]["relative_gain"]["hi"], INK, "o", "white")
    axC.text(xi[-1] * 0.95, 100 * h["relative_gain"] + 5.5, "actual visit diagnosis\n(post-decision)",
             fontsize=7, va="bottom", ha="right")
    axC.set_xlim(16, 200)
    axC.set_xticks(xi)
    axC.set_xticklabels([str(x) for x in xi])
    axC.set_xlabel("Diagnostic classes (ICD-10, log scale)")
    axC.set_ylim(0, 30)
    axC.set_yticks([0, 10, 20, 30])
    axC.set_ylabel(r"$\Delta L/L_D$ (%)")
    panel_letter(axC, "C", x=-0.2, y=1.0)

    handles = [
        Line2D([], [], ls="-", lw=1, color=BLUE, marker="o", ms=5, mfc=BLUE, label=r"20-class $\hat{D}$, confirmatory"),
        Line2D([], [], ls="-", lw=1, color=VERM, marker="D", ms=4.5, mfc=VERM, label=r"CCSR $\hat{D}$, post-confirmatory exploratory"),
        Line2D([], [], ls="-", lw=1, color=VERM, marker="s", ms=4.5, mfc=VERM, label=r"ICD-10 $\hat{D}$, post-confirmatory exploratory"),
        Line2D([], [], ls="-", lw=1, color=INK, marker="o", ms=4.5, mfc="white", label="actual visit diagnosis (post-decision)"),
        Line2D([], [], ls="none", marker="o", ms=4.5, mfc=INK, mec=INK, label="Model D log loss"),
        Line2D([], [], ls="none", marker="^", ms=5, mfc=GREEN, mec=GREEN, label="Model D+X log loss"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=3,
               handlelength=2.0, columnspacing=1.6)
    save(fig, name)


# ====================================================================== Figure S1
def figS1():
    name = "figS1_calibration"
    analyses = [("primary", "Primary"), ("S1", "SA1 hard top-1"), ("S2", "SA2 ICD-10 chapter"),
                ("S3", "SA3 race and\nethnicity added"), ("S4", "SA4 chronological split")]
    W, H = DOUBLE_MM, 125
    fig, axs = plt.subplots(2, 3, figsize=(W * MM, H * MM))
    fig.subplots_adjust(left=0.07, right=0.985, top=0.95, bottom=0.09, wspace=0.32, hspace=0.42)
    LIM = 0.23
    suppressed_total = 0
    for i, ((key, lab), ax) in enumerate(zip(analyses, axs.flat)):
        rel = f"results/mcmed/stageG_test_{key}.json"
        sm = load(rel)["summary"]
        note_src(name, lab, rel, ["summary.deciles_D", "summary.deciles_DX", "summary.n", "summary.events"])
        ax.plot([0, LIM], [0, LIM], color=GREY, lw=0.6, ls=(0, (3, 2)))
        ax.axhspan(-0.03, -0.004, color="#F0F0F0", lw=0)
        for dk, col, mk, yoff in (("deciles_D", BLUE, "o", -0.012), ("deciles_DX", VERM, "^", -0.022)):
            shown = [(d["mean_pred"], d["observed"]) for d in sm[dk]
                     if is_shown(d["events"]) and d["observed"] is not None]
            hidden = [d["mean_pred"] for d in sm[dk]
                      if not (is_shown(d["events"]) and d["observed"] is not None)]
            suppressed_total += len(hidden)
            if shown:
                ax.plot([p for p, _ in shown], [o for _, o in shown], ls="-", lw=0.7, color=col,
                        marker=mk, ms=3.8, mfc=col, mec=col)
            ax.plot(hidden, [yoff] * len(hidden), ls="none", marker="|", ms=4, color=col, mew=0.8)
        ax.set_xlim(0, LIM)
        ax.set_ylim(-0.03, LIM)
        ax.set_xticks([0, 0.05, 0.10, 0.15, 0.20])
        ax.set_yticks([0, 0.05, 0.10, 0.15, 0.20])
        ax.set_xticklabels(["0", "0.05", "0.10", "0.15", "0.20"])
        ax.set_yticklabels(["0", "0.05", "0.10", "0.15", "0.20"])
        ax.set_aspect("equal")
        ax.text(0.005, LIM * 0.98, lab, fontsize=7, va="top", ha="left")
        ax.text(LIM * 0.99, 0.002, f"test n = {count_txt(sm['n'])}\n{count_txt(sm['events'])} events",
                fontsize=7, va="bottom", ha="right")
        panel_letter(ax, "ABCDE"[i], x=-0.12, y=1.0)
        if i % 3 == 0:
            ax.set_ylabel("Observed ICU proportion")
        if i >= 2:
            ax.set_xlabel("Mean predicted probability")
    lg = axs.flat[5]
    lg.axis("off")
    handles = [Line2D([], [], color=BLUE, marker="o", ms=4, lw=0.7, label="Model D"),
               Line2D([], [], color=VERM, marker="^", ms=4, lw=0.7, label="Model D+X"),
               Line2D([], [], color=GREY, lw=0.6, ls=(0, (3, 2)), label="perfect calibration"),
               Line2D([], [], color=INK, marker="|", ls="none", ms=7, mew=1.0, label="decile with <10 events:\nobserved value not shown\n(tick at mean predicted)")]
    lg.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 1.0), handlelength=2.2, labelspacing=0.9)
    lg.text(0.0, 0.18, "Deciles of predicted risk, formed\nseparately for each model.",
            fontsize=7, color=MUTED, transform=lg.transAxes, va="top")
    save(fig, name)
    return suppressed_total


# ====================================================================== Figure S2
def figS2():
    name = "figS2_attrition"
    rc = "results/mcmed/stageA_cohort.json"
    rs = "results/mcmed/stageC_split.json"
    coh, spl = load(rc), load(rs)
    note_src(name, "flow", rc, ["attrition[*] (visits, patients, icu, excluded)", "unmapped_breakdown"])
    note_src(name, "split", rs, ["by_set.dev", "by_set.test", "patient_overlap"])
    keep_lab = {
        "all_visits": "All ED visits",
        "admitted (Inpatient/Observation/ICU)": "Admitted (inpatient, observation, or ICU)",
        "valid Arrival_time and Dispo_time": "Valid arrival and disposition times",
        "age >= 18": "Age 18 years or older",
        "Dispo_time > T": "Disposition after T",
        "decision_time = min(Dispo_time, first ADT order) > T": "Decision time after T",
        "no ICU / critical-care consult at or before T": "No ICU or critical-care consult by T",
        "primary CCSR mapping available (unmapped excluded)": "Analysis cohort (CCSR mapping available)",
    }
    exc_lab = {
        "valid Arrival_time and Dispo_time": "Invalid arrival or disposition time",
        "age >= 18": "Age under 18 years",
        "Dispo_time > T": "Disposition documented by T",
        "decision_time = min(Dispo_time, first ADT order) > T": "Admission or transfer order by T\n(decision time = earlier of the two)",
        "no ICU / critical-care consult at or before T": "ICU or critical-care consult by T",
        "primary CCSR mapping available (unmapped excluded)": "No CCSR mapping",
    }

    def icu_txt(icu):
        if not is_shown(icu["n"]):
            return "ICU <10"
        return f"ICU {count_txt(icu['n'])} ({icu['pct']:.1f}%)"

    steps = coh["attrition"]
    W, H = DOUBLE_MM, 172
    fig, ax = canvas(W, H)
    bw, bh, x0 = 74, 11, 8
    gap = 18.5
    ytop = H - 4 - bh
    for i, st in enumerate(steps):
        y = ytop - i * gap
        final = i == len(steps) - 1
        box(ax, x0, y, bw, bh,
            f"{keep_lab[st['step']]}\n{count_txt(st['visits'])} visits; {count_txt(st['patients'])} patients; "
            f"{icu_txt(st['icu'])}",
            fc=FILL_LIGHT if final else "white", ec=BLUE if final else INK)
        if i:
            arrow(ax, x0 + bw / 2, y + gap, x0 + bw / 2, y + bh)
        if "excluded" in st:
            e = st["excluded"]
            ey = y + bh + (gap - bh) / 2
            text = f"{exc_lab[st['step']]}\n{count_txt(e['visits'])} visits; {icu_txt(e['icu'])}"
            eh = 10
            if st["step"].startswith("primary CCSR"):
                ub = coh["unmapped_breakdown"]
                text += (f"\ncode not in CCSR {count_txt(ub['code not in CCSR'])}; "
                         f"missing ICD-10 {count_txt(ub['missing Dx_ICD10'])}")
                eh = 13
            box(ax, 100, ey - eh / 2, 84, eh, text, fc=FILL_GREY, ec=GREY)
            ax.plot([x0 + bw / 2, 100], [ey, ey], color=INK, lw=0.7)
    # split
    yl = ytop - (len(steps) - 1) * gap
    ys = yl - 22
    dv, ts = spl["by_set"]["dev"], spl["by_set"]["test"]
    for xx, d, lab, fc, ec in ((4, dv, "Development set", FILL_LIGHT, BLUE), (52, ts, "Locked test set", FILL_WARM, VERM)):
        box(ax, xx, ys, 44, 13,
            f"{lab}\n{count_txt(d['visits'])} visits\n{count_txt(d['patients'])} patients; {icu_txt(d['icu'])}",
            fc=fc, ec=ec)
        arrow(ax, x0 + bw / 2, yl, xx + 22, ys + 13)
    ax.text(100, ys + 6.5, f"Salted hash of patient identifier;\npatient overlap {spl['patient_overlap']}",
            fontsize=7, color=MUTED, va="center")
    save(fig, name)


def main():
    fig1()
    fig2()
    fig3()
    fig4()
    n_sup = figS1()
    figS2()
    SOURCES["_meta"] = {
        "generated_by": "figures/make_figures.py",
        "disclosure_rule": "counts < 10 (including 0) shown as '<10' or not displayed",
        "figS1_suppressed_decile_points": n_sup,
    }
    (HERE / "figure_sources.json").write_text(json.dumps(SOURCES, indent=2, ensure_ascii=False) + "\n")
    print("done")


if __name__ == "__main__":
    main()
