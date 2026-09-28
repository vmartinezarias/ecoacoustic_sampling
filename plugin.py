"""MILEVA Processing provider and in-app help dialog."""

from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QAction, QIcon, QPixmap
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTextBrowser, QVBoxLayout
from qgis.core import QgsApplication

from .provider import EcoacousticProvider

ROOT = Path(__file__).resolve().parent
DOI = "https://doi.org/10.1007/s10980-026-02372-5"


class EcoacousticSamplingPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.help_action = None

    def initGui(self):
        self.provider = EcoacousticProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)
        self.help_action = QAction(QIcon(str(ROOT / "icon.svg")), "MILEVA · Inicio", self.iface.mainWindow())
        self.help_action.triggered.connect(self.show_help)
        self.iface.addPluginToMenu("MILEVA", self.help_action)

    def show_help(self):
        dialog = QDialog(self.iface.mainWindow())
        dialog.setWindowTitle("MILEVA")
        dialog.resize(590, 530)
        layout = QVBoxLayout(dialog)
        title = QLabel("MILEVA · Diseño espacial de muestreo ecoacústico")
        title.setWordWrap(True)
        layout.addWidget(title)
        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(QPixmap(str(ROOT / "logo_gha.png")).scaledToWidth(
            350, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(logo)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(
            "<p>Abre <b>Caja de herramientas de Procesos → MILEVA</b>. "
            "Sigue los pasos II–VI para escalar el proxy, segmentar el paisaje, "
            "seleccionar puntos, extraer medias y comparar distribuciones. "
            "El paso VII requiere interpretación científica.</p>"
            "<p>Usa un CRS proyectado en metros. La generación SLIC no se ejecuta "
            "desde MILEVA; puedes cargar polígonos SLIC preparados por otro método. "
            "Genera un escenario completo y uno aleatorio desde un área poligonal "
            "o ráster. Compara las salidas de Step V como capas separadas.</p>"
            "<p><b>Autores:</b> Victor M. Martínez-Arias, Carolina Paniagua-Villada, "
            "Maria José Guerrero y Juan Daza.</p>"
            "<p><b>Grupo Herpetológico de Antioquia - GHA:</b> "
            "<a href='https://grupoherpetologicodeantioquia.org/'>"
            "grupoherpetologicodeantioquia.org</a></p>"
            "<p><b>Cita:</b> Martínez-Arias, V. M., Paniagua-Villada, C., "
            "Guerrero, M. J., &amp; Daza, J. M. (2026). <i>A workflow to optimize "
            "spatial sampling in ecoacoustic studies.</i> Landscape Ecology, 41, "
            "article 126. <a href='" + DOI + "'>" + DOI + "</a>. "
            "Información suplementaria S10.</p>"
            "<p>Consulta README.md dentro del paquete para instrucciones y límites "
            "de cada algoritmo.</p>"
        )
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def unload(self):
        if self.help_action is not None:
            self.iface.removePluginMenu("MILEVA", self.help_action)
            self.help_action = None
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
