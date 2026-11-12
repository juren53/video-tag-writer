"""
VideoTagWriter - MetadataPanel widget (dynamic metadata form).
"""

import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit,
    QFormLayout, QScrollArea, QSizePolicy, QMainWindow,
)
from PyQt6.QtCore import Qt

from ..metadata import field_tags, storable_in_sidecar

logger = logging.getLogger(__name__)

_MP4_ONLY_NOTE = "Not stored for MPG/MPEG — this field has no XMP tag (MP4 only)."


class MetadataPanel(QWidget):
    """
    Form panel for displaying and editing metadata fields.
    Fields are built dynamically from the active mode's field spec.
    """

    def __init__(self, metadata_manager, parent=None):
        super().__init__(parent)
        self.metadata_manager = metadata_manager
        self._field_widgets = {}    # label -> QLineEdit | QTextEdit
        self._row_labels = {}       # label -> QLabel (form row label)
        self._char_labels = {}      # label -> QLabel (for text widgets)
        self._all_text_fields = []
        self._scroll = None
        self._outer_layout = None
        self._sidecar_mode = False
        self._setup_ui()
        self._install_event_filters()

    # -- UI construction -----------------------------------------------------

    def _setup_ui(self):
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)

        self._storage_banner = QLabel()
        self._storage_banner.setWordWrap(True)
        self._storage_banner.setStyleSheet("font-size: 8pt; padding: 2px 4px;")
        self._storage_banner.hide()
        self._outer_layout.addWidget(self._storage_banner)

        self._build_form()

        self.write_button = QPushButton("Write Metadata")
        self.write_button.setToolTip("Save metadata  (Ctrl+S)")
        self.write_button.clicked.connect(self._on_write)
        self._outer_layout.addWidget(self.write_button, alignment=Qt.AlignmentFlag.AlignHCenter)

    @staticmethod
    def _tooltip_for(spec: dict) -> str:
        tags = field_tags(spec)
        lines = [f"Primary: {tags[0]}"] if tags else []
        if len(tags) > 1:
            lines.append("Also written: " + ", ".join(tags[1:]))
        if spec.get('date_field'):
            lines.append("Format: YYYY, YYYY-MM or YYYY-MM-DD")
        if spec.get('list_field'):
            lines.append("Separate multiple values with ';'")
        if spec.get('int_field'):
            lines.append("Whole number")
        return "\n".join(lines)

    def _build_form(self):
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        for spec in self.metadata_manager.get_field_specs():
            label_text = spec['label']
            widget_type = spec.get('widget', 'line')
            max_chars = spec.get('max_chars', 2000)
            if widget_type == 'hidden':
                continue

            row_label = QLabel(f"{label_text}:")
            tip = self._tooltip_for(spec)
            row_label.setToolTip(tip)

            if widget_type == 'text':
                container, widget, char_label = self._make_text_widget(label_text, max_chars)
                self._char_labels[label_text] = char_label
                form.addRow(row_label, container)
            else:
                widget = QLineEdit()
                widget.setMaxLength(max_chars)
                if spec.get('date_field'):
                    widget.setPlaceholderText("YYYY-MM-DD")
                elif spec.get('list_field'):
                    widget.setPlaceholderText("value; value; …")
                form.addRow(row_label, widget)

            widget.setToolTip(tip)
            widget.setProperty('base_tooltip', tip)
            self._field_widgets[label_text] = widget
            self._row_labels[label_text] = row_label
            self._all_text_fields.append(widget)

        form_widget = QWidget()
        form_widget.setLayout(form)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(form_widget)
        self._outer_layout.insertWidget(1, self._scroll, 1)
        self._apply_sidecar_state()

    def rebuild_fields(self):
        """Tear down and rebuild form widgets from the current mode spec."""
        if self._scroll is not None:
            self._outer_layout.removeWidget(self._scroll)
            self._scroll.hide()          # don't linger on screen until deleteLater runs
            self._scroll.deleteLater()
            self._scroll = None
        self._field_widgets = {}
        self._row_labels = {}
        self._char_labels = {}
        self._all_text_fields = []
        self._build_form()
        self._install_event_filters()

    def _make_text_widget(self, label, max_chars):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        widget = QTextEdit()
        widget.setAcceptRichText(False)
        widget.setMinimumHeight(80)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(widget)
        char_label = QLabel(f"0/{max_chars} characters")
        char_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        char_label.setStyleSheet("font-size: 8pt;")
        layout.addWidget(char_label)
        widget.textChanged.connect(lambda lbl=label, mc=max_chars: self._update_char_count(lbl, mc))
        return container, widget, char_label

    def _install_event_filters(self):
        for w in self._all_text_fields:
            w.installEventFilter(self)

    def eventFilter(self, watched, event):
        """Keep Up/Down inside text fields instead of navigating files."""
        if (event.type() == event.Type.KeyPress
                and watched in self._all_text_fields
                and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)):
            event.accept()
            watched.event(event)
            return True
        return super().eventFilter(watched, event)

    # -- sidecar mode --------------------------------------------------------

    def set_sidecar_mode(self, enabled: bool):
        """Grey out fields that cannot be stored in an XMP sidecar (MPG/MPEG files)."""
        self._sidecar_mode = enabled
        self._apply_sidecar_state()

    def _apply_sidecar_state(self):
        specs = {s['label']: s for s in self.metadata_manager.get_field_specs()}
        blocked = []
        for label, widget in self._field_widgets.items():
            spec = specs.get(label, {})
            ok = (not self._sidecar_mode) or storable_in_sidecar(spec)
            widget.setEnabled(ok)
            row_label = self._row_labels.get(label)
            if row_label:
                row_label.setEnabled(ok)
            base = widget.property('base_tooltip') or ''
            widget.setToolTip(base if ok else f"{base}\n\n{_MP4_ONLY_NOTE}")
            if not ok:
                blocked.append(label)
        if self._sidecar_mode:
            text = "MPG/MPEG file — metadata is stored in an XMP sidecar (<name>.xmp) beside the video."
            if blocked:
                text += "  Greyed-out fields are MP4-only: " + ", ".join(blocked) + "."
            self._storage_banner.setText(text)
            self._storage_banner.show()
        else:
            self._storage_banner.hide()

    # -- data sync -----------------------------------------------------------

    @staticmethod
    def _widget_text(widget) -> str:
        return widget.toPlainText() if isinstance(widget, QTextEdit) else widget.text()

    def update_from_manager(self):
        for spec in self.metadata_manager.get_field_specs():
            label = spec['label']
            widget = self._field_widgets.get(label)
            if widget is None:
                continue
            value = self.metadata_manager.get_field(label)
            if isinstance(widget, QTextEdit):
                widget.blockSignals(True)
                widget.setPlainText(value)
                widget.blockSignals(False)
                self._update_char_count(label, spec.get('max_chars', 2000))
            else:
                widget.setText(value)
                widget.setCursorPosition(0)

    def update_manager_from_ui(self):
        for spec in self.metadata_manager.get_field_specs():
            widget = self._field_widgets.get(spec['label'])
            if widget is not None:
                self.metadata_manager.set_field(spec['label'], self._widget_text(widget))

    def has_unsaved_edits(self) -> bool:
        for spec in self.metadata_manager.get_field_specs():
            widget = self._field_widgets.get(spec['label'])
            if widget is not None and self._widget_text(widget) != self.metadata_manager.get_field(spec['label']):
                return True
        return False

    # -- character counting --------------------------------------------------

    def _update_char_count(self, label, max_chars):
        char_label = self._char_labels.get(label)
        widget = self._field_widgets.get(label)
        if not char_label or not isinstance(widget, QTextEdit):
            return
        text = widget.toPlainText()
        count = len(text)
        if count > max_chars:
            widget.blockSignals(True)
            widget.setPlainText(text[:max_chars])
            widget.blockSignals(False)
            count = max_chars
        char_label.setText(f"{count}/{max_chars} characters")
        if count >= max_chars:
            char_label.setStyleSheet("font-size: 8pt; color: red;")
        elif count > max_chars * 0.8:
            char_label.setStyleSheet("font-size: 8pt; color: #FF9900;")
        else:
            char_label.setStyleSheet("font-size: 8pt;")

    # -- write button --------------------------------------------------------

    def _on_write(self):
        main = self.window()
        if isinstance(main, QMainWindow) and hasattr(main, 'on_save'):
            main.on_save()
