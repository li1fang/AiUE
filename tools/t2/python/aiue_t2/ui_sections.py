from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aiue_t2.state import PreviewImageRecord, ReportRecord, report_payload_to_text


class SummaryCard(QFrame):
    def __init__(self, *, title: str, object_name: str) -> None:
        super().__init__()
        self.setObjectName(object_name)
        self.setProperty("card", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        title_label = QLabel(title)
        title_label.setProperty("role", "muted")
        self.value_label = QLabel("0")
        self.value_label.setObjectName(f"{object_name}Value")
        self.value_label.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))


class DetailsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.details_header = QLabel("No report selected")
        self.details_header.setProperty("role", "muted")
        self.details_text = QPlainTextEdit()
        self.details_text.setObjectName("detailsJsonText")
        self.details_text.setReadOnly(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.details_header)
        layout.addWidget(self.details_text)

    def render_report(self, report: ReportRecord | None) -> None:
        if report is None:
            self.details_header.setText("No report selected")
            self.details_text.setPlainText("{}")
            return
        self.details_header.setText(
            f"{report.gate_id or report.name} | {report.status.upper()} | {report.generated_at_utc or 'unknown time'}"
        )
        self.details_text.setPlainText(report_payload_to_text(report))


class ImagesPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.preview_records_by_key: dict[str, PreviewImageRecord] = {}

        self.preview_list = QListWidget()
        self.preview_list.setObjectName("previewImageList")
        self.preview_label = QLabel("No preview image selected")
        self.preview_label.setObjectName("previewImageLabel")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(320)
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("border: 1px solid #334155; border-radius: 8px;")

        preview_splitter = QSplitter()
        preview_splitter.addWidget(self.preview_list)
        preview_splitter.addWidget(self.preview_label)

        self.metrics_table = QTableWidget(0, 7)
        self.metrics_table.setObjectName("r3MetricsTable")
        self.metrics_table.setHorizontalHeaderLabels(
            [
                "Package",
                "Shot",
                "Status",
                "Crop Hist L1",
                "Crop Mean Delta",
                "Full Hist L1",
                "Full Mean Delta",
            ]
        )
        self.metrics_table.horizontalHeader().setStretchLastSection(True)

        metrics_box = QGroupBox("Before / After Metrics")
        metrics_layout = QVBoxLayout(metrics_box)
        metrics_layout.addWidget(self.metrics_table)

        layout = QVBoxLayout(self)
        layout.addWidget(preview_splitter)
        layout.addWidget(metrics_box)

    def set_preview_records(self, records: list[PreviewImageRecord], selected_key: str | None) -> None:
        self.preview_list.clear()
        self.preview_records_by_key.clear()
        for record in records:
            item = QListWidgetItem(f"{record.section} | {record.title}")
            item.setData(Qt.UserRole, record.key)
            self.preview_list.addItem(item)
            self.preview_records_by_key[record.key] = record
        if selected_key:
            for index in range(self.preview_list.count()):
                item = self.preview_list.item(index)
                if item.data(Qt.UserRole) == selected_key:
                    self.preview_list.setCurrentItem(item)
                    break
        if self.preview_list.currentItem() is None and self.preview_list.count():
            self.preview_list.setCurrentRow(0)

    def preview_record(self, image_key: str | None) -> PreviewImageRecord | None:
        if not image_key:
            return None
        return self.preview_records_by_key.get(image_key)

    def render_selected_image(self, preview: PreviewImageRecord | None) -> None:
        if not preview:
            self.preview_label.setText("No preview image selected")
            self.preview_label.setPixmap(QPixmap())
            return
        pixmap = QPixmap(preview.image_path)
        if pixmap.isNull():
            self.preview_label.setText(f"Preview not available:\n{preview.image_path}")
            self.preview_label.setPixmap(QPixmap())
            return
        scaled = pixmap.scaled(
            max(self.preview_label.width(), 640),
            max(self.preview_label.height(), 360),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)
        self.preview_label.setText("")

    def render_metrics(self, rows: list[dict]) -> None:
        self.metrics_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("package_id") or "",
                row.get("shot_id") or "",
                row.get("status") or "",
                f"{float(row.get('crop_histogram_l1') or 0.0):.6f}",
                f"{float(row.get('crop_mean_abs_pixel_delta') or 0.0):.6f}",
                f"{float(row.get('full_histogram_l1') or 0.0):.6f}",
                f"{float(row.get('full_mean_abs_pixel_delta') or 0.0):.6f}",
            ]
            for column_index, value in enumerate(values):
                self.metrics_table.setItem(row_index, column_index, QTableWidgetItem(str(value)))


class SlotDebuggerPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.slot_table = QTableWidget(0, 8)
        self.slot_table.setObjectName("slotDebuggerTable")
        self.slot_table.setHorizontalHeaderLabels(
            [
                "Package",
                "Slot",
                "Kind",
                "Component",
                "Socket",
                "Coverages",
                "Conflicts",
                "Superseded",
            ]
        )
        self.slot_table.horizontalHeader().setStretchLastSection(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.slot_table)

    def render_slot_packages(self, packages: list[dict]) -> None:
        rows: list[list[str]] = []
        for package in packages:
            package_id = str(package.get("package_id") or "")
            for slot in list(package.get("slots") or []):
                attach_state = dict(slot.get("attach_state") or {})
                component = dict(slot.get("managed_component") or {})
                binding = dict(slot.get("binding") or {})
                coverages = ", ".join(
                    f"{item.get('shot_id')}:{float(item.get('coverage_ratio') or 0.0):.4f}"
                    for item in list(slot.get("tracked_coverages") or [])
                )
                rows.append(
                    [
                        package_id,
                        str(slot.get("slot_name") or ""),
                        str(binding.get("item_kind") or ""),
                        str(component.get("component_name") or ""),
                        str(
                            attach_state.get("resolved_attach_socket_name")
                            or attach_state.get("requested_attach_socket_name")
                            or ""
                        ),
                        coverages,
                        str(len(list(slot.get("slot_conflicts") or []))),
                        str(len(list(slot.get("superseded_bindings") or []))),
                    ]
                )
        self.slot_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                self.slot_table.setItem(row_index, column_index, QTableWidgetItem(value))
