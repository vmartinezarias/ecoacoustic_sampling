"""STEP II - Landscape proxy selection: rescale a continuous raster to [1, 100].

Notebook equivalent: the rasterio `rescale_raster()` helper.
Here we delegate to the native 'Rescale raster' algorithm, which is more
robust than re-reading the band with numpy and handles nodata cleanly.
"""

from ..citation import CITATION

import processing
from qgis.core import (
    Qgis,
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingException,
)


class RescaleProxyAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    NEW_MIN = "NEW_MIN"
    NEW_MAX = "NEW_MAX"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(self.INPUT, "Landscape proxy (continuous raster)")
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.NEW_MIN, "New minimum",
                type=Qgis.ProcessingNumberParameterType.Double, defaultValue=1.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.NEW_MAX, "New maximum",
                type=Qgis.ProcessingNumberParameterType.Double, defaultValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(self.OUTPUT, "Rescaled proxy")
        )

    def processAlgorithm(self, parameters, context, feedback):
        new_min = self.parameterAsDouble(parameters, self.NEW_MIN, context)
        new_max = self.parameterAsDouble(parameters, self.NEW_MAX, context)

        if new_max <= new_min:
            raise QgsProcessingException("New maximum must exceed new minimum.")

        result = processing.run(
            "native:rescaleraster",
            {
                "INPUT": parameters[self.INPUT],
                "BAND": 1,
                "MINIMUM": new_min,
                "MAXIMUM": new_max,
                "NODATA": None,
                "OUTPUT": parameters[self.OUTPUT],
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        return {self.OUTPUT: result["OUTPUT"]}

    # --- boilerplate ---
    def name(self):
        return "rescale_proxy"

    def displayName(self):
        return "STEP II - Rescale landscape proxy (1-100)"

    def group(self):
        return "Workflow steps"

    def groupId(self):
        return "workflow"

    def shortHelpString(self):
        return (
            "Rescales a continuous landscape proxy (e.g. a spectral index or a "
            "fusion layer) to a fixed range, by default 1-100, so that downstream "
            "tessellation behaves consistently regardless of the proxy's native units."
        ) + CITATION

    def createInstance(self):
        return RescaleProxyAlgorithm()
