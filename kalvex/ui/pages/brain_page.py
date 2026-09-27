"""Bot Brain page — the automated decision pipeline made visible:

    ANALYSE › DECIDE › SIZE › EXECUTE › MANAGE › REVIEW

plus per-strategy state and the self-improvement review log with bounded,
auditable parameter suggestions (never touches risk ceilings).
"""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from kalvex.ui.theme import mono_font
from kalvex.ui.widgets import (
    hint_label,
    legend,
    make_table,
    page_header,
    section_title,
)

STAGES = ["ANALYSE", "DECIDE", "SIZE", "EXECUTE", "MANAGE", "REVIEW"]
STAGE_COLORS = {
    "ANALYSE": "#8B7CFF", "DECIDE": "#FFB020", "SIZE": "#35D0C8",
    "EXECUTE": "#E8EEF6", "MANAGE": "#FF8A3D", "REVIEW": "#8B7CFF",
}


class PipelineChip(QFrame):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.setObjectName("chip")
        self.setFixedHeight(52)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(1)
        t = legend(name)
        t.setStyleSheet(f"color: {STAGE_COLORS[name]};")
        lay.addWidget(t)
        self.detail = legend("idle", faint=True)
        lay.addWidget(self.detail)
        self.set_active(False)

    def set_active(self, active: bool, detail: str = "") -> None:
        c = STAGE_COLORS[self.name] if active else "#222B36"
        self.setStyleSheet(
            f"QFrame#chip {{ border: 1px solid {c}; "
            f"border-left: 3px solid {STAGE_COLORS[self.name]}; }}")
        if detail:
            self.detail.setText(detail[:26])

    def set_last(self, text: str) -> None:
        self.detail.setText(text[:26])
        self.set_active(True, text)


class BrainPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(10)

        root.addWidget(page_header(
            "Bot Brain",
            "Full transparency: every cycle the bot analyses, decides, sizes, "
            "executes, manages and reviews — each step is journalled with its "
            "reasoning. No black-box ML; self-improvement stays inside hard bands."))

        # ---- pipeline chevrons -----------------------------------------
        pipe_row = QHBoxLayout()
        pipe_row.setSpacing(6)
        self.chips: dict[str, PipelineChip] = {}
        for i, st in enumerate(STAGES):
            chip = PipelineChip(st)
            self.chips[st] = chip
            pipe_row.addWidget(chip, stretch=1)
            if i < len(STAGES) - 1:
                arrow = legend("›")
                arrow.setStyleSheet("color: #4A5665; font-size: 16px;")
                pipe_row.addWidget(arrow)
        root.addLayout(pipe_row)

        # ---- strategy state cards + reviews ------------------------------
        body = QHBoxLayout()
        body.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(section_title("STRATEGY STATE"))
        self.strat_table = make_table(
            ["Strategy", "Enabled", "Params (editable band)", "Last Thought"],
            stretch_cols=(0, 2, 3))
        self.strat_table.setMinimumHeight(200)
        left.addWidget(self.strat_table)

        left.addWidget(section_title("SELF-IMPROVEMENT REVIEWS (BOUNDED)"))
        self.reviews_table = make_table(
            ["Time", "Strategy", "Stats", "Suggestion", "Applied"],
            stretch_cols=(2, 3))
        self.reviews_table.setMinimumHeight(140)
        left.addWidget(self.reviews_table)
        left.addWidget(hint_label(
            "Suggestions only move soft parameters inside hard-coded bands "
            "(TUNE_BANDS) and never touch risk ceilings. A strategy that loses "
            "5+ times in a row is auto-disabled and needs manual re-arm."))

        left_w = QWidget()
        left_w.setLayout(left)
        body.addWidget(left_w, stretch=3)

        # live thought feed (mono)
        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(section_title("REASONING LOG"))
        self.thoughts = QPlainTextEdit()
        self.thoughts.setReadOnly(True)
        self.thoughts.setFont(mono_font(10))
        self.thoughts.setStyleSheet(
            "background-color: #10151C; border: 1px solid #222B36;")
        right.addWidget(self.thoughts, stretch=1)
        right_w = QWidget()
        right_w.setLayout(right)
        right_w.setFixedWidth(420)
        body.addWidget(right_w)

        root.addLayout(body, stretch=1)

    # ------------------------------------------------------------------ #
    def on_thought(self, ev: dict) -> None:
        stage = ev.get("stage", "")
        chip = self.chips.get(stage)
        if chip:
            chip.set_last(ev.get("text", ""))
        self.thoughts.appendHtml(
            f'<span style="color:#4A5665">{ev.get("ts","")}</span> '
            f'<span style="color:{STAGE_COLORS.get(stage, "#E8EEF6")}; '
            f'font-weight:700">[{stage}]</span> '
            f'<span style="color:#E8EEF6">{ev.get("text","")}</span>')
        sb = self.thoughts.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_strategies(self, rows: list[dict]) -> None:
        self.strat_table.setRowCount(len(rows))
        from PySide6.QtWidgets import QTableWidgetItem
        for r, row in enumerate(rows):
            self.strat_table.setItem(r, 0, QTableWidgetItem(row["name"]))
            self.strat_table.setItem(
                r, 1, QTableWidgetItem("ON" if row["enabled"] else "OFF"))
            self.strat_table.setItem(r, 2, QTableWidgetItem(row["params"]))
            self.strat_table.setItem(r, 3, QTableWidgetItem(row["last"]))

    def set_reviews(self, rows: list[dict]) -> None:
        from PySide6.QtWidgets import QTableWidgetItem
        self.reviews_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            try:
                stats = json.loads(row["stats"] or "{}")
                sug = json.loads(row["suggestion"] or "{}")
            except json.JSONDecodeError:
                stats, sug = {}, {}
            stat_txt = (f"n={stats.get('n','?')} wr={stats.get('win_rate', 0):.0%} "
                        f"exp=₹{stats.get('expectancy', 0):,.0f}"
                        if stats else "—")
            self.reviews_table.setItem(r, 0, QTableWidgetItem(row["ts"]))
            self.reviews_table.setItem(r, 1, QTableWidgetItem(row["strategy_key"]))
            self.reviews_table.setItem(r, 2, QTableWidgetItem(stat_txt))
            self.reviews_table.setItem(
                r, 3, QTableWidgetItem(json.dumps(sug) if sug else "no change"))
            self.reviews_table.setItem(
                r, 4, QTableWidgetItem("YES" if row["applied"] else "—"))
