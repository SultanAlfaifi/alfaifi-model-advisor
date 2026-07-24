from __future__ import annotations

import html
import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .installer import install_model
from .models import HardwareProfile, Recommendation, UserNeeds
from .service import AdvisorService, DiscoveryResult


X_URL = "https://x.com/SultAlfaifi"
LINKEDIN_URL = "https://www.linkedin.com/in/alfaifi-sultan/"
GITHUB_URL = "https://github.com/SultanAlfaifi/mustakshif"

GOALS = (
    ("general", "General chat"),
    ("writing", "Writing & summaries"),
    ("coding", "Programming"),
    ("agents", "Agents & tools"),
    ("vision", "Images & vision"),
    ("ui_design", "UI design"),
    ("documents", "Documents & PDFs"),
    ("translation", "Translation"),
    ("reasoning", "Research & reasoning"),
)

WAITING_TIPS = (
    "Reading the official Ollama catalog — no model is downloaded.",
    "Checking model sizes, context windows, and device memory.",
    "Comparing language, task, speed, quality, and license preferences.",
    "Keeping the process local, explainable, and approval-gated.",
)

AR_WAITING_TIPS = (
    "نقرأ فهرس Ollama الرسمي — لن يتم تنزيل أي نموذج.",
    "نتحقق من الأحجام وسعة السياق وذاكرة جهازك.",
    "نقارن اللغة والمهمة والسرعة والجودة وتفضيلات الترخيص.",
    "كل خطوة محلية وقابلة للتفسير، والتنزيل يحتاج موافقتك.",
)

TEXT = {
    "en": {
        "tagline": "The local AI model explorer",
        "privacy": "PRIVATE BY DESIGN",
        "nav_device": "01  Device",
        "nav_preferences": "02  Preferences",
        "nav_discovery": "03  Discovery",
        "nav_results": "04  Results",
        "language": "LANGUAGE",
        "welcome_eyebrow": "BUILT FOR THIS DEVICE",
        "welcome_title": "Meet the model\nthat fits your machine.",
        "welcome_body": "Mustakshif reads your hardware locally, learns what you want to build, then explores trusted official sources for the strongest practical match.",
        "scan": "Start private device scan",
        "scan_note": "No account. No telemetry. No automatic downloads.",
        "feature_private": "Private",
        "feature_private_body": "Hardware and answers stay here.",
        "feature_live": "Current",
        "feature_live_body": "Official model data is refreshed daily.",
        "feature_clear": "Explainable",
        "feature_clear_body": "Every recommendation shows why.",
        "prefs_title": "Shape your ideal model",
        "prefs_body": "A few choices turn hundreds of models into a shortlist built around you.",
        "experience": "EXPERIENCE",
        "language_field": "PRIMARY LANGUAGE",
        "priority": "TOP PRIORITY",
        "locality": "WHERE IT RUNS",
        "context": "CONTEXT SIZE",
        "goals": "WHAT WILL YOU USE IT FOR?",
        "beginner": "Beginner",
        "intermediate": "Intermediate",
        "advanced": "Advanced",
        "arabic": "Arabic",
        "english": "English",
        "both_languages": "Arabic & English",
        "balanced": "Balanced",
        "speed": "Maximum speed",
        "quality": "Maximum quality",
        "memory": "Lowest memory use",
        "local": "Local only",
        "local_cloud": "Local + cloud",
        "cloud": "Cloud is acceptable",
        "short": "Short conversations",
        "medium": "Files & projects",
        "long": "Large repositories",
        "goal_general": "General chat",
        "goal_writing": "Writing & summaries",
        "goal_coding": "Programming",
        "goal_agents": "Agents & tools",
        "goal_vision": "Images & vision",
        "goal_ui": "UI design",
        "goal_documents": "Documents & PDFs",
        "goal_translation": "Translation",
        "goal_reasoning": "Research & reasoning",
        "vision": "Must understand images",
        "tools": "Needs tool calling",
        "permissive": "Permissive licenses only",
        "back": "Back",
        "discover": "Discover my best models",
        "waiting_eyebrow": "EXPLORING TRUSTED SOURCES",
        "waiting_title": "Your shortlist is taking shape.",
        "waiting_start": "Opening the official model catalog…",
        "results_title": "Your best-fit models",
        "adjust": "Adjust preferences",
        "best": "BEST MATCH",
        "choice": "CHOICE {number}",
        "category_best_overall": "BEST OVERALL",
        "category_best_quality": "HIGHEST QUALITY",
        "category_fastest": "FASTEST",
        "category_lightest": "LIGHTEST",
        "category_most_popular": "MOST POPULAR",
        "score_components": "Device {hardware} · Task {task} · Language {language} · Speed {speed} · Quality {quality} · Community {community} · Freshness {freshness}",
        "confidence": "{value} confidence",
        "context_detail": "{value}K starting context",
        "download": "{value} GB download",
        "open_page": "Open official page",
        "copy": "Copy install command",
        "install": "Install with Ollama",
        "license": "License: {value}",
        "empty_title": "No model satisfies every selected requirement.",
        "empty_body": "Try allowing cloud models or relaxing image, tool-calling, or license requirements.",
        "choose_goal_title": "Choose a goal",
        "choose_goal_body": "Select at least one intended use.",
        "hardware_scanning": "Inspecting CPU, memory, GPU, storage, and Ollama…",
        "catalog_opening": "Opening the official model catalog…",
        "creator": "Created by Sultan Alfaifi",
    },
    "ar": {
        "tagline": "مستكشف نماذج الذكاء الاصطناعي المحلية",
        "privacy": "خصوصية افتراضية",
        "nav_device": "٠١  الجهاز",
        "nav_preferences": "٠٢  التفضيلات",
        "nav_discovery": "٠٣  الاستكشاف",
        "nav_results": "٠٤  النتائج",
        "language": "اللغة",
        "welcome_eyebrow": "مصمم خصيصًا لهذا الجهاز",
        "welcome_title": "اكتشف النموذج\nالذي يناسب جهازك.",
        "welcome_body": "يفحص مستكشف جهازك محليًا، ويفهم ما تريد إنجازه، ثم يبحث في المصادر الرسمية الموثوقة عن أفضل خيار عملي لك.",
        "scan": "ابدأ فحص الجهاز بخصوصية",
        "scan_note": "بلا حساب، بلا تتبع، وبلا تنزيل تلقائي.",
        "feature_private": "خاص",
        "feature_private_body": "مواصفات الجهاز وإجاباتك تبقى محليًا.",
        "feature_live": "متجدد",
        "feature_live_body": "تُحدّث بيانات النماذج الرسمية يوميًا.",
        "feature_clear": "واضح",
        "feature_clear_body": "كل توصية تشرح أسباب اختيارها.",
        "prefs_title": "صمّم نموذجك المثالي",
        "prefs_body": "اختيارات قليلة تحوّل مئات النماذج إلى قائمة تناسب احتياجك.",
        "experience": "مستوى الخبرة",
        "language_field": "اللغة الأساسية",
        "priority": "الأولوية",
        "locality": "مكان التشغيل",
        "context": "حجم السياق",
        "goals": "فيمَ ستستخدم النموذج؟",
        "beginner": "مبتدئ",
        "intermediate": "متوسط",
        "advanced": "متقدم",
        "arabic": "العربية",
        "english": "الإنجليزية",
        "both_languages": "العربية والإنجليزية",
        "balanced": "توازن بين الجودة والسرعة",
        "speed": "أعلى سرعة",
        "quality": "أعلى جودة",
        "memory": "أقل استهلاك للذاكرة",
        "local": "محلي فقط",
        "local_cloud": "محلي وسحابي",
        "cloud": "السحابة مقبولة",
        "short": "محادثات قصيرة",
        "medium": "ملفات ومشاريع",
        "long": "مستودعات كبيرة",
        "goal_general": "محادثة عامة",
        "goal_writing": "الكتابة والتلخيص",
        "goal_coding": "البرمجة",
        "goal_agents": "الوكلاء والأدوات",
        "goal_vision": "الصور والرؤية",
        "goal_ui": "تصميم الواجهات",
        "goal_documents": "المستندات وPDF",
        "goal_translation": "الترجمة",
        "goal_reasoning": "البحث والاستدلال",
        "vision": "يجب أن يفهم الصور",
        "tools": "يحتاج استدعاء الأدوات",
        "permissive": "تراخيص متساهلة فقط",
        "back": "رجوع",
        "discover": "اكتشف أفضل النماذج لي",
        "waiting_eyebrow": "استكشاف المصادر الموثوقة",
        "waiting_title": "نجهّز قائمتك المختصرة.",
        "waiting_start": "جارٍ فتح فهرس النماذج الرسمي…",
        "results_title": "النماذج الأنسب لك",
        "adjust": "تعديل التفضيلات",
        "best": "الخيار الأفضل",
        "choice": "الخيار {number}",
        "category_best_overall": "الأفضل إجمالًا",
        "category_best_quality": "أعلى جودة",
        "category_fastest": "الأسرع",
        "category_lightest": "الأخف",
        "category_most_popular": "الأكثر شعبية",
        "score_components": "الجهاز {hardware} · المهمة {task} · اللغة {language} · السرعة {speed} · الجودة {quality} · المجتمع {community} · الحداثة {freshness}",
        "confidence": "ثقة {value}",
        "context_detail": "سياق ابتدائي {value}K",
        "download": "تنزيل {value} GB",
        "open_page": "فتح الصفحة الرسمية",
        "copy": "نسخ أمر التثبيت",
        "install": "التثبيت عبر Ollama",
        "license": "الترخيص: {value}",
        "empty_title": "لا يوجد نموذج يحقق جميع المتطلبات المحددة.",
        "empty_body": "جرّب السماح بالنماذج السحابية أو تخفيف متطلبات الصور أو الأدوات أو الترخيص.",
        "choose_goal_title": "اختر هدفًا",
        "choose_goal_body": "حدد استخدامًا واحدًا على الأقل.",
        "hardware_scanning": "نفحص المعالج والذاكرة والبطاقة الرسومية والتخزين وOllama…",
        "catalog_opening": "جارٍ فتح فهرس النماذج الرسمي…",
        "creator": "صُنع بواسطة Sultan Alfaifi",
    },
}

APP_STYLE = """
QWidget {
    background: #08101f;
    color: #e8eefb;
    font-family: "Segoe UI";
    font-size: 14px;
}
QMainWindow { background: #08101f; }
QLabel { background: transparent; }
QFrame#sidebar {
    background: #0c172b;
    border: 1px solid #1d3153;
    border-radius: 24px;
}
QFrame#topbar {
    background: transparent;
    border: 0;
}
QFrame#featureCard {
    background: #0c172b;
    border: 1px solid #1b3156;
    border-radius: 15px;
}
QFrame#card {
    background: #0d1730;
    border: 1px solid #20345e;
    border-radius: 18px;
}
QFrame#bestCard {
    background: #0d1b35;
    border: 2px solid #3b82f6;
    border-radius: 18px;
}
QLabel#brand {
    color: #67e8f9;
    font-size: 28px;
    font-weight: 800;
    letter-spacing: 2px;
}
QLabel#sidebarTagline {
    color: #8ea0be;
    font-size: 12px;
}
QLabel#navStep {
    color: #71829f;
    font-size: 14px;
    font-weight: 650;
    padding: 11px 13px;
    border-radius: 9px;
}
QLabel#navStepActive {
    color: #ffffff;
    background: #162b4d;
    border-left: 3px solid #38bdf8;
    font-size: 14px;
    font-weight: 750;
    padding: 11px 13px;
    border-radius: 9px;
}
QLabel#hero {
    color: #ffffff;
    font-size: 34px;
    font-weight: 800;
}
QLabel#section {
    color: #ffffff;
    font-size: 23px;
    font-weight: 750;
}
QLabel#muted { color: #91a2c2; }
QLabel#eyebrow {
    color: #67e8f9;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#score {
    color: #67e8f9;
    font-size: 25px;
    font-weight: 800;
}
QPushButton {
    background: #2563eb;
    color: white;
    border: 0;
    border-radius: 11px;
    padding: 11px 18px;
    font-weight: 700;
}
QPushButton:hover { background: #3b82f6; }
QPushButton:pressed { background: #1d4ed8; }
QPushButton:disabled { background: #263651; color: #73809a; }
QPushButton#secondary {
    background: #14223d;
    border: 1px solid #315185;
}
QPushButton#secondary:hover { background: #1c3158; }
QPushButton#language {
    background: #101f38;
    border: 1px solid #2b416c;
    padding: 7px 10px;
    font-size: 12px;
}
QPushButton#languageActive {
    background: #e9f8ff;
    color: #071226;
    padding: 7px 10px;
    font-size: 12px;
}
QComboBox {
    background: #0a1428;
    border: 1px solid #2b416c;
    border-radius: 10px;
    padding: 10px 12px;
    min-height: 20px;
}
QComboBox QAbstractItemView {
    background: #111d35;
    selection-background-color: #2563eb;
}
QCheckBox {
    background: #0a1428;
    border: 1px solid #243b65;
    border-radius: 10px;
    padding: 10px;
}
QCheckBox:checked {
    background: #102c54;
    border-color: #38bdf8;
}
QProgressBar {
    background: #13213b;
    border: 0;
    border-radius: 7px;
    min-height: 14px;
}
QProgressBar::chunk {
    background: #38bdf8;
    border-radius: 7px;
}
QScrollArea { border: 0; }
"""


def _asset_path(name: str) -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "assets" / name
    return Path(__file__).resolve().parents[2] / "assets" / name


class Worker(QThread):
    progress = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[Callable[[str], None]], object]) -> None:
        super().__init__()
        self.operation = operation

    def run(self) -> None:
        try:
            self.succeeded.emit(self.operation(self.progress.emit))
        except Exception as exc:  # surfaced to the desktop instead of disappearing
            self.failed.emit(str(exc))


def _label(text: str, object_name: str | None = None, *, wrap: bool = False) -> QLabel:
    value = QLabel(text)
    if object_name:
        value.setObjectName(object_name)
    value.setWordWrap(wrap)
    return value


class MustakshifWindow(QMainWindow):
    def __init__(self, language: str = "en") -> None:
        super().__init__()
        self.language = language
        self.setWindowTitle(f"Mustakshif {__version__}")
        self.setMinimumSize(1040, 720)
        self.resize(1240, 840)
        icon_path = _asset_path("mustakshif-icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.hardware: HardwareProfile | None = None
        self.discovery: DiscoveryResult | None = None
        self.worker: Worker | None = None
        self.waiting_tip_index = 0
        self.waiting_timer = QTimer(self)
        self.waiting_timer.setInterval(2800)
        self.waiting_timer.timeout.connect(self._rotate_waiting_tip)
        self._build_interface()

    def _t(self, key: str, **values: object) -> str:
        return TEXT[self.language][key].format(**values)

    def _build_interface(self, page_index: int = 0) -> None:
        root = QWidget()
        root.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if self.language == "ar" else Qt.LayoutDirection.LeftToRight
        )
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(22, 22, 22, 22)
        root_layout.setSpacing(22)
        root_layout.addWidget(self._build_sidebar())

        content = QFrame()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 0, 4, 0)
        content_layout.setSpacing(10)
        content_layout.addWidget(self._build_topbar())
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_welcome_page())
        self.pages.addWidget(self._build_preferences_page())
        self.pages.addWidget(self._build_waiting_page())
        self.pages.addWidget(self._build_results_page())
        self.pages.currentChanged.connect(self._update_steps)
        content_layout.addWidget(self.pages, 1)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)
        self.pages.setCurrentIndex(page_index)
        self._update_steps(page_index)
        if self.hardware:
            self._show_hardware_summary()
        if self.discovery and page_index == 3:
            self._render_results(self.discovery)

    def _build_sidebar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("sidebar")
        frame.setFixedWidth(248)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(22, 24, 22, 20)
        layout.setSpacing(14)

        logo_path = _asset_path("mustakshif-icon.png")
        if logo_path.exists():
            logo = QLabel()
            logo.setPixmap(
                QPixmap(str(logo_path)).scaled(
                    56,
                    56,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            logo.setFixedSize(56, 56)
            layout.addWidget(logo)
        layout.addWidget(_label("MUSTAKSHIF", "brand"))
        layout.addWidget(_label(self._t("tagline"), "sidebarTagline", wrap=True))
        layout.addSpacing(18)

        self.step_labels = [
            _label(self._t("nav_device"), "navStep"),
            _label(self._t("nav_preferences"), "navStep"),
            _label(self._t("nav_discovery"), "navStep"),
            _label(self._t("nav_results"), "navStep"),
        ]
        for step in self.step_labels:
            layout.addWidget(step)

        layout.addStretch()
        layout.addWidget(_label(self._t("privacy"), "eyebrow"))
        layout.addWidget(_label(self._t("language"), "sidebarTagline"))
        language_row = QHBoxLayout()
        english = QPushButton("English")
        arabic = QPushButton("العربية")
        english.setObjectName("languageActive" if self.language == "en" else "language")
        arabic.setObjectName("languageActive" if self.language == "ar" else "language")
        english.clicked.connect(lambda: self._switch_language("en"))
        arabic.clicked.connect(lambda: self._switch_language("ar"))
        language_row.addWidget(english)
        language_row.addWidget(arabic)
        layout.addLayout(language_row)
        creator = QLabel(
            f'{self._t("creator")}<br><a href="{X_URL}">X</a> · '
            f'<a href="{LINKEDIN_URL}">LinkedIn</a> · <a href="{GITHUB_URL}">GitHub</a>'
        )
        creator.setTextFormat(Qt.TextFormat.RichText)
        creator.setOpenExternalLinks(True)
        creator.setWordWrap(True)
        creator.setStyleSheet("color:#71829f; font-size:11px;")
        layout.addWidget(creator)
        return frame

    def _build_topbar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("topbar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.addWidget(_label(self._t("tagline"), "muted"))
        layout.addStretch()
        layout.addWidget(_label(f"v{__version__}  •  Windows", "eyebrow"))
        return frame

    def _switch_language(self, language: str) -> None:
        if language == self.language or (self.worker and self.worker.isRunning()):
            return
        page_index = self.pages.currentIndex()
        self.language = language
        self._build_interface(page_index)

    def _update_steps(self, page_index: int) -> None:
        if not hasattr(self, "step_labels"):
            return
        for index, label in enumerate(self.step_labels):
            label.setObjectName("navStepActive" if index == page_index else "navStep")
            label.style().unpolish(label)
            label.style().polish(label)

    def _build_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 28, 28, 18)
        layout.addStretch()
        layout.addWidget(_label(self._t("welcome_eyebrow"), "eyebrow"))
        hero = _label(self._t("welcome_title"), "hero")
        layout.addWidget(hero)
        intro = _label(self._t("welcome_body"), "muted", wrap=True)
        intro.setMaximumWidth(720)
        layout.addWidget(intro)
        layout.addSpacing(18)

        features = QHBoxLayout()
        features.setSpacing(12)
        for title_key, body_key in (
            ("feature_private", "feature_private_body"),
            ("feature_live", "feature_live_body"),
            ("feature_clear", "feature_clear_body"),
        ):
            card = QFrame()
            card.setObjectName("featureCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.addWidget(_label(self._t(title_key), "eyebrow"))
            card_layout.addWidget(_label(self._t(body_key), "muted", wrap=True))
            features.addWidget(card)
        layout.addLayout(features)
        layout.addSpacing(18)

        action_row = QHBoxLayout()
        scan = QPushButton(self._t("scan"))
        scan.setMinimumWidth(230)
        scan.clicked.connect(self.start_scan)
        action_row.addWidget(scan)
        action_row.addWidget(_label(self._t("scan_note"), "muted", wrap=True))
        action_row.addStretch()
        layout.addLayout(action_row)
        layout.addStretch()
        return page

    def _field(self, title: str, widget: QWidget) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(7)
        layout.addWidget(_label(title, "eyebrow"))
        layout.addWidget(widget)
        return layout

    def _combo(self, entries: tuple[tuple[str, str], ...], default: int = 0) -> QComboBox:
        combo = QComboBox()
        for value, title in entries:
            combo.addItem(title, value)
        combo.setCurrentIndex(default)
        return combo

    def _build_preferences_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 10, 14, 18)
        layout.setSpacing(18)

        layout.addWidget(_label(self._t("prefs_title"), "section"))
        layout.addWidget(_label(self._t("prefs_body"), "muted", wrap=True))
        self.hardware_summary = _label("", "muted", wrap=True)
        layout.addWidget(self.hardware_summary)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)
        self.experience = self._combo(
            (
                ("beginner", self._t("beginner")),
                ("intermediate", self._t("intermediate")),
                ("advanced", self._t("advanced")),
            ),
            1,
        )
        self.language_choice = self._combo(
            (("ar", self._t("arabic")), ("en", self._t("english")), ("both", self._t("both_languages"))),
            2,
        )
        self.priority = self._combo(
            (
                ("balanced", self._t("balanced")),
                ("speed", self._t("speed")),
                ("quality", self._t("quality")),
                ("memory", self._t("memory")),
            )
        )
        self.locality = self._combo(
            (("local", self._t("local")), ("both", self._t("local_cloud")), ("cloud", self._t("cloud")))
        )
        self.context_size = self._combo(
            (("short", self._t("short")), ("medium", self._t("medium")), ("long", self._t("long"))),
            1,
        )
        grid.addLayout(self._field(self._t("experience"), self.experience), 0, 0)
        grid.addLayout(self._field(self._t("language_field"), self.language_choice), 0, 1)
        grid.addLayout(self._field(self._t("priority"), self.priority), 1, 0)
        grid.addLayout(self._field(self._t("locality"), self.locality), 1, 1)
        grid.addLayout(self._field(self._t("context"), self.context_size), 2, 0, 1, 2)
        layout.addLayout(grid)

        layout.addWidget(_label(self._t("goals"), "eyebrow"))
        goal_grid = QGridLayout()
        goal_grid.setHorizontalSpacing(12)
        goal_grid.setVerticalSpacing(10)
        self.goal_checks: dict[str, QCheckBox] = {}
        goal_keys = {
            "general": "goal_general",
            "writing": "goal_writing",
            "coding": "goal_coding",
            "agents": "goal_agents",
            "vision": "goal_vision",
            "ui_design": "goal_ui",
            "documents": "goal_documents",
            "translation": "goal_translation",
            "reasoning": "goal_reasoning",
        }
        for index, (value, _title) in enumerate(GOALS):
            # QAbstractButton treats a single ampersand as a keyboard mnemonic.
            check = QCheckBox(self._t(goal_keys[value]).replace("&", "&&"))
            check.setChecked(value == "general")
            self.goal_checks[value] = check
            goal_grid.addWidget(check, index // 3, index % 3)
        layout.addLayout(goal_grid)

        options = QHBoxLayout()
        self.vision = QCheckBox(self._t("vision"))
        self.tools = QCheckBox(self._t("tools"))
        self.permissive = QCheckBox(self._t("permissive"))
        options.addWidget(self.vision)
        options.addWidget(self.tools)
        options.addWidget(self.permissive)
        layout.addLayout(options)

        actions = QHBoxLayout()
        back = QPushButton(self._t("back"))
        back.setObjectName("secondary")
        back.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        discover = QPushButton(self._t("discover"))
        discover.clicked.connect(self.start_discovery)
        actions.addWidget(back)
        actions.addStretch()
        actions.addWidget(discover)
        layout.addLayout(actions)
        scroll.setWidget(page)
        return scroll

    def _build_waiting_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(70, 70, 70, 70)
        layout.addStretch()
        layout.addWidget(_label(self._t("waiting_eyebrow"), "eyebrow"))
        layout.addWidget(_label(self._t("waiting_title"), "hero"))
        self.waiting_status = _label(self._t("waiting_start"), "muted", wrap=True)
        layout.addWidget(self.waiting_status)
        layout.addSpacing(18)
        progress = QProgressBar()
        progress.setRange(0, 0)
        layout.addWidget(progress)
        tips = AR_WAITING_TIPS if self.language == "ar" else WAITING_TIPS
        self.waiting_tip = _label(tips[0], "muted", wrap=True)
        layout.addWidget(self.waiting_tip)
        layout.addStretch(2)
        return page

    def _build_results_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 10)
        top = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.addWidget(_label(self._t("results_title"), "section"))
        self.results_summary = _label("", "muted", wrap=True)
        title_col.addWidget(self.results_summary)
        top.addLayout(title_col)
        top.addStretch()
        again = QPushButton(self._t("adjust"))
        again.setObjectName("secondary")
        again.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        top.addWidget(again)
        layout.addLayout(top)

        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setSpacing(14)
        self.results_scroll.setWidget(self.results_container)
        layout.addWidget(self.results_scroll, 1)
        return page

    def _build_footer(self) -> QWidget:
        footer = QLabel(
            f'Created by <b>Sultan Alfaifi</b> &nbsp;·&nbsp; '
            f'<a href="{X_URL}">X</a> &nbsp;·&nbsp; '
            f'<a href="{LINKEDIN_URL}">LinkedIn</a> &nbsp;·&nbsp; '
            f'<a href="{GITHUB_URL}">GitHub</a> &nbsp;&nbsp; '
            f'<span style="color:#667796">© 2026 · Apache-2.0</span>'
        )
        footer.setTextFormat(Qt.TextFormat.RichText)
        footer.setOpenExternalLinks(True)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color:#91a2c2; padding: 5px;")
        return footer

    def _run_worker(
        self,
        operation: Callable[[Callable[[str], None]], object],
        success: Callable[[object], None],
    ) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.worker = Worker(operation)
        self.worker.progress.connect(lambda message: self.waiting_status.setText(self._progress_message(message)))
        self.worker.succeeded.connect(success)
        self.worker.failed.connect(self._show_error)
        self.worker.start()

    def start_scan(self) -> None:
        self.pages.setCurrentIndex(2)
        self.waiting_status.setText(self._t("hardware_scanning"))
        self.waiting_timer.start()
        self._run_worker(lambda _progress: AdvisorService().scan_device(), self._scan_complete)

    def _scan_complete(self, value: object) -> None:
        self.waiting_timer.stop()
        self.hardware = value if isinstance(value, HardwareProfile) else None
        if not self.hardware:
            self._show_error("The hardware scan returned an unexpected result.")
            return
        self._show_hardware_summary()
        self.pages.setCurrentIndex(1)

    def _show_hardware_summary(self) -> None:
        if not self.hardware or not hasattr(self, "hardware_summary"):
            return
        if self.language == "ar":
            gpu = (
                f"{self.hardware.best_gpu.name} · ذاكرة رسومية {self.hardware.best_gpu.vram_gb} GB"
                if self.hardware.best_gpu
                else "لم تُكتشف ذاكرة بطاقة رسومية منفصلة"
            )
            ollama = (
                self.hardware.ollama.version or "جاهز"
                if self.hardware.ollama.installed
                else "غير مثبت"
            )
            text = (
                f"{self.hardware.cpu}  •  ذاكرة {self.hardware.ram_gb} GB  •  {gpu}  •  "
                f"مساحة حرة {self.hardware.free_disk_gb} GB  •  Ollama: {ollama}"
            )
        else:
            gpu = (
                f"{self.hardware.best_gpu.name} · {self.hardware.best_gpu.vram_gb} GB VRAM"
                if self.hardware.best_gpu
                else "No discrete GPU memory detected"
            )
            ollama = (
                self.hardware.ollama.version or "Ready"
                if self.hardware.ollama.installed
                else "Not installed"
            )
            text = (
                f"{self.hardware.cpu}  •  {self.hardware.ram_gb} GB RAM  •  {gpu}  •  "
                f"{self.hardware.free_disk_gb} GB free  •  Ollama: {ollama}"
            )
        self.hardware_summary.setText(text)

    def _selected_needs(self) -> UserNeeds | None:
        goals = [name for name, control in self.goal_checks.items() if control.isChecked()]
        if not goals:
            QMessageBox.information(self, self._t("choose_goal_title"), self._t("choose_goal_body"))
            return None
        needs_vision = self.vision.isChecked() or any(goal in {"vision", "ui_design"} for goal in goals)
        needs_tools = self.tools.isChecked() or "agents" in goals
        return UserNeeds(
            experience=str(self.experience.currentData()),
            goals=goals,
            language=str(self.language_choice.currentData()),
            priority=str(self.priority.currentData()),
            locality=str(self.locality.currentData()),
            needs_vision=needs_vision,
            needs_tools=needs_tools,
            context_size=str(self.context_size.currentData()),
            permissive_license_only=self.permissive.isChecked(),
        )

    def start_discovery(self) -> None:
        if not self.hardware:
            self.start_scan()
            return
        needs = self._selected_needs()
        if not needs:
            return
        self.pages.setCurrentIndex(2)
        self.waiting_status.setText(self._t("catalog_opening"))
        self.waiting_tip_index = 0
        tips = AR_WAITING_TIPS if self.language == "ar" else WAITING_TIPS
        self.waiting_tip.setText(tips[0])
        self.waiting_timer.start()
        self._run_worker(
            lambda progress: AdvisorService().discover(
                needs,
                hardware=self.hardware,
                progress=progress,
            ),
            self._discovery_complete,
        )

    def _discovery_complete(self, value: object) -> None:
        self.waiting_timer.stop()
        if not isinstance(value, DiscoveryResult):
            self._show_error("Model discovery returned an unexpected result.")
            return
        self.discovery = value
        self._render_results(value)
        self.pages.setCurrentIndex(3)

    def _clear_results(self) -> None:
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _render_results(self, result: DiscoveryResult) -> None:
        self._clear_results()
        if self.language == "ar":
            source = {
                "live": "المصادر الرسمية المباشرة",
                "index": "الفهرس اليومي التلقائي الموثوق",
                "cache": "النسخة المحلية الموثوقة",
                "bundled": "الفهرس الموثوق المضمن مع التطبيق",
                "seed": "الفهرس الاحتياطي المضمن",
            }.get(result.source_state, result.source_state)
            summary = (
                f"فحصنا {result.discovered_families} عائلة رسمية، وتحققنا من "
                f"{result.verified_families} عائلة، وقارنّا {result.candidate_count} نسخة قابلة للتشغيل "
                f"باستخدام {source}."
            )
        else:
            source = {
                "live": "live official sources",
                "index": "the trusted automatic daily index",
                "cache": "the trusted local cache",
                "bundled": "the trusted catalog bundled with the app",
                "seed": "the bundled trusted fallback",
            }.get(result.source_state, result.source_state)
            summary = (
                f"Scanned {result.discovered_families} official families, verified "
                f"{result.verified_families}, and compared {result.candidate_count} runnable variants "
                f"using {source}."
            )
        self.results_summary.setText(summary)
        if not result.recommendations:
            empty = QFrame()
            empty.setObjectName("card")
            box = QVBoxLayout(empty)
            box.setContentsMargins(22, 22, 22, 22)
            box.addWidget(_label(self._t("empty_title"), "section"))
            box.addWidget(_label(self._t("empty_body"), "muted", wrap=True))
            self.results_layout.addWidget(empty)
        else:
            for index, recommendation in enumerate(result.recommendations):
                self.results_layout.addWidget(self._recommendation_card(recommendation, index))
        self.results_layout.addStretch()

    def _recommendation_card(self, item: Recommendation, index: int) -> QWidget:
        model = item.model
        card = QFrame()
        card.setObjectName("bestCard" if index == 0 else "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(9)

        top = QHBoxLayout()
        title_col = QVBoxLayout()
        category_key = {
            "best_overall": "category_best_overall",
            "best_quality": "category_best_quality",
            "fastest": "category_fastest",
            "lightest": "category_lightest",
            "most_popular": "category_most_popular",
        }.get(item.category)
        rank = self._t(category_key) if category_key else (
            self._t("best") if index == 0 else self._t("choice", number=index + 1)
        )
        title_col.addWidget(_label(rank, "eyebrow"))
        title_col.addWidget(_label(html.escape(model.display_name), "section"))
        top.addLayout(title_col)
        top.addStretch()
        score = _label(f"{item.score}/100", "score")
        score.setAlignment(Qt.AlignmentFlag.AlignRight)
        top.addWidget(score)
        layout.addLayout(top)

        mode_labels = (
            {
                "full_gpu": "تشغيل كامل على البطاقة الرسومية",
                "hybrid": "البطاقة الرسومية + ذاكرة النظام",
                "cpu": "المعالج + ذاكرة النظام",
                "cloud": "سحابي",
            }
            if self.language == "ar"
            else {
                "full_gpu": "Full GPU",
                "hybrid": "GPU + system RAM",
                "cpu": "CPU / system RAM",
                "cloud": "Cloud",
            }
        )
        confidence = {"High": "عالية", "Medium": "متوسطة", "Low": "منخفضة"}.get(
            item.confidence, item.confidence
        ) if self.language == "ar" else item.confidence
        details = [
            mode_labels[item.hardware_mode],
            self._t("context_detail", value=item.recommended_context_k),
            self._t("confidence", value=confidence),
        ]
        if model.size_gb is not None:
            details.insert(1, self._t("download", value=model.size_gb))
        layout.addWidget(_label("  •  ".join(details), "muted", wrap=True))

        if item.score_breakdown:
            component_text = self._t(
                "score_components",
                **{name: f"{item.score_breakdown.get(name, 0):.1f}" for name in (
                    "hardware",
                    "task",
                    "language",
                    "speed",
                    "quality",
                    "community",
                    "freshness",
                )},
            )
            layout.addWidget(_label(component_text, "muted", wrap=True))

        reasons = "<br>".join(f"• {html.escape(self._localize_reason(reason))}" for reason in item.reasons)
        reason_label = QLabel(reasons)
        reason_label.setTextFormat(Qt.TextFormat.RichText)
        reason_label.setWordWrap(True)
        layout.addWidget(reason_label)

        license_text = _label(self._t("license", value=model.license_name), "muted", wrap=True)
        layout.addWidget(license_text)
        for warning in item.warnings:
            warning_label = _label(f"⚠ {self._localize_warning(warning)}", "muted", wrap=True)
            warning_label.setStyleSheet("color:#fbbf24;")
            layout.addWidget(warning_label)

        actions = QHBoxLayout()
        official = QPushButton(self._t("open_page"))
        official.setObjectName("secondary")
        official.clicked.connect(lambda _checked=False, url=model.official_url: QDesktopServices.openUrl(QUrl(url)))
        actions.addWidget(official)
        if model.install_command:
            copy = QPushButton(self._t("copy"))
            copy.setObjectName("secondary")
            copy.clicked.connect(
                lambda _checked=False, command=model.install_command: QApplication.clipboard().setText(command or "")
            )
            actions.addWidget(copy)
            install = QPushButton(self._t("install"))
            install.clicked.connect(lambda _checked=False, choice=item: self._confirm_install(choice))
            actions.addWidget(install)
        actions.addStretch()
        layout.addLayout(actions)
        return card

    def _progress_message(self, message: str) -> str:
        if self.language != "ar":
            return message
        if message.startswith("Downloading the small automatic"):
            return "جارٍ تنزيل فهرس مستكشف اليومي الصغير — لا يتم تنزيل أي نموذج…"
        if message.startswith("Opening the official Ollama"):
            return "جارٍ فتح مكتبة Ollama الرسمية…"
        if message.startswith("Opening the complete official Ollama"):
            return "جارٍ فتح مكتبة Ollama الرسمية الكاملة…"
        if message.startswith("Found "):
            return "اكتمل فحص العائلات الرسمية، ونحدد الآن الأنسب لإجاباتك…"
        if message.startswith("Verified "):
            numbers = [part for part in message.split() if "/" in part]
            progress = numbers[0] if numbers else ""
            return f"تم التحقق من {progress} عائلة — نجهز القائمة المختصرة…"
        if message.startswith("Scoring "):
            return "نقارن النماذج القابلة للتشغيل مع احتياجاتك…"
        return "نستكشف المصادر الرسمية الموثوقة…"

    def _localize_reason(self, reason: str) -> str:
        if self.language != "ar":
            return reason
        if reason.startswith("Task fit:"):
            value = reason.split(":", 1)[1].split(" for", 1)[0].strip()
            return f"ملاءمة المهمة: {value} للأهداف المحددة."
        if reason.startswith("Language fit:"):
            value = reason.split(":", 1)[1].strip()
            return f"ملاءمة اللغة: {value}"
        if reason.startswith("Community adoption:"):
            value = reason.split(":", 1)[1].strip()
            return f"الانتشار المجتمعي: {value}"
        if reason.startswith("Freshness:"):
            value = reason.split(":", 1)[1].strip()
            return f"حداثة النموذج: {value}"
        known = {
            "The model fits inside the GPU after a 10% VRAM safety margin.": "يتوقع أن يعمل النموذج داخل البطاقة الرسومية بعد تطبيق هامش أمان 10% للذاكرة.",
            "The model can run with weights distributed between GPU and system RAM.": "يمكن تشغيل النموذج بتوزيع الأوزان بين البطاقة الرسومية وذاكرة النظام.",
            "The model can run through system RAM and CPU execution.": "يمكن تشغيل النموذج باستخدام المعالج وذاكرة النظام.",
            "The model runs remotely, so local model memory is not required.": "يعمل النموذج عن بُعد، لذلك لا يحتاج إلى ذاكرة محلية لتخزين أوزانه.",
        }
        return known.get(reason, reason)

    def _localize_warning(self, warning: str) -> str:
        if self.language != "ar":
            return warning
        known = {
            "The official entry does not expose a machine-readable license; verify the model page before use.": "لا يعرض الإدخال الرسمي ترخيصًا قابلًا للقراءة آليًا؛ تحقق من صفحة النموذج قبل الاستخدام.",
            "No standardized benchmark score is indexed; quality uses a transparent size-and-capability proxy.": "لا تتوفر نتيجة معيارية موحدة؛ لذلك تستخدم الجودة تقديرًا شفافًا يعتمد على الحجم والقدرات.",
            "The estimated fit is close to total VRAM, so a 10% safety margin classifies it as hybrid.": "الاستهلاك المقدر قريب من كامل ذاكرة البطاقة؛ لذلك يصنفه هامش الأمان 10% كتشكيل هجين.",
            "Part of the model may be offloaded to system RAM, so it will be slower than full GPU execution.": "قد يتم نقل جزء من النموذج إلى ذاكرة النظام، لذلك سيكون أبطأ من التشغيل الكامل على البطاقة الرسومية.",
        }
        return known.get(warning, warning)

    def _confirm_install(self, item: Recommendation) -> None:
        if not self.hardware or not self.hardware.ollama.installed:
            title = "Ollama مطلوب" if self.language == "ar" else "Ollama is required"
            body = (
                "ثبّت Ollama أولًا، ثم أعد فتح مستكشف لتثبيت هذا النموذج."
                if self.language == "ar"
                else "Install Ollama first, then reopen Mustakshif to install this model."
            )
            QMessageBox.information(
                self,
                title,
                body,
            )
            return
        model = item.model
        title = "الموافقة على تنزيل النموذج" if self.language == "ar" else "Approve model download"
        question = (
            f"هل تريد تنفيذ هذا الأمر الموثوق؟\n\n{model.install_command}\n\n"
            f"حجم التنزيل التقريبي: {model.size_gb or 'غير معروف'} GB"
            if self.language == "ar"
            else f"Run this trusted command?\n\n{model.install_command}\n\n"
            f"Approximate download: {model.size_gb or 'unknown'} GB"
        )
        answer = QMessageBox.question(
            self,
            title,
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.pages.setCurrentIndex(2)
        self.waiting_status.setText(
            f"جارٍ تثبيت {model.display_name} عبر Ollama…"
            if self.language == "ar"
            else f"Installing {model.display_name} with Ollama…"
        )
        self.waiting_timer.start()
        self._run_worker(
            lambda _progress: install_model(model, self.hardware),
            lambda code: self._install_complete(model.display_name, int(code)),
        )

    def _install_complete(self, model_name: str, code: int) -> None:
        self.waiting_timer.stop()
        self.pages.setCurrentIndex(3)
        if code == 0:
            QMessageBox.information(
                self,
                "اكتمل التثبيت" if self.language == "ar" else "Installation complete",
                f"{model_name} جاهز الآن في Ollama."
                if self.language == "ar"
                else f"{model_name} is ready in Ollama.",
            )
        else:
            QMessageBox.critical(
                self,
                "خطأ في Ollama" if self.language == "ar" else "Ollama error",
                f"توقف Ollama برمز {code}."
                if self.language == "ar"
                else f"Ollama exited with code {code}.",
            )

    def _rotate_waiting_tip(self) -> None:
        tips = AR_WAITING_TIPS if self.language == "ar" else WAITING_TIPS
        self.waiting_tip_index = (self.waiting_tip_index + 1) % len(tips)
        self.waiting_tip.setText(tips[self.waiting_tip_index])

    def _show_error(self, message: str) -> None:
        self.waiting_timer.stop()
        target = 1 if self.hardware else 0
        self.pages.setCurrentIndex(target)
        QMessageBox.critical(
            self,
            "تعذر على مستكشف المتابعة" if self.language == "ar" else "Mustakshif could not continue",
            message,
        )


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Mustakshif")
    app.setOrganizationName("Sultan Alfaifi")
    app.setStyleSheet(APP_STYLE)
    window = MustakshifWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
