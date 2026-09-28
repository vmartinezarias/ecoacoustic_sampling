"""Processing provider grouping the seven workflow steps."""

from pathlib import Path

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .algorithms.rescale_proxy import RescaleProxyAlgorithm
from .algorithms.watershed_tessellation import WatershedTessellationAlgorithm
from .algorithms.sampling_points import SamplingPointsAlgorithm
from .algorithms.random_sampling import RandomSamplingAlgorithm
from .algorithms.buffer_zonal import BufferZonalAlgorithm
from .algorithms.statistical_comparison import StatisticalComparisonAlgorithm


class EcoacousticProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        algorithms = [
            RescaleProxyAlgorithm,            # STEP II
            WatershedTessellationAlgorithm,   # STEP III (a) basins / half-basins
            RandomSamplingAlgorithm,         # complete grid + random subset
            SamplingPointsAlgorithm,          # STEP IV  pole of inaccessibility
            BufferZonalAlgorithm,             # STEP V   buffer + zonal stats
            StatisticalComparisonAlgorithm,   # STEP VI  KS + Wasserstein
        ]
        for alg in algorithms:
            self.addAlgorithm(alg())

    def id(self):
        return "mileva"

    def name(self):
        return "MILEVA"

    def longName(self):
        return "MILEVA - Mapping-Informed Landscape Ecotopes for Versatile Acoustic Sampling"

    def icon(self):
        return QIcon(str(Path(__file__).resolve().parent / "icon.svg"))
