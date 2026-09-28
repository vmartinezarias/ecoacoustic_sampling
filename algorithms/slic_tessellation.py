"""Step IIIb: polygonize S10 labels, or use optional GRASS SLIC addon.

R/supercells in Supplementary Information S10 is the reference implementation.
GRASS i.superpixels.slic is an optional alternative and may not be exposed by
QGIS Processing without a manually installed addon description.
"""

from ..citation import CITATION

import math

import processing
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink,
    QgsProcessingException,
)



class SlicTessellationAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    RADIUS = "RADIUS"
    COMPACTNESS = "COMPACTNESS"
    SEGMENTED = "SEGMENTED"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(self.INPUT, "Landscape proxy (rescaled)")
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RADIUS, "Recorder radius (meters)",
                type=Qgis.ProcessingNumberParameterType.Double, defaultValue=200.0, minValue=1.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.COMPACTNESS, "Compactness",
                type=Qgis.ProcessingNumberParameterType.Double, defaultValue=1.0, minValue=0.0,
            )
        )
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.SEGMENTED, "Existing SLIC labels raster (optional; skips GRASS addon)", optional=True))
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, "SLIC tiles")
        )

    def processAlgorithm(self, parameters, context, feedback):
        labels = self.parameterAsRasterLayer(parameters, self.SEGMENTED, context)
        if labels is not None:
            slic_raster = parameters[self.SEGMENTED]
        else:
            slic_raster = self._run_addon(parameters, context, feedback)

        poly = processing.run("gdal:polygonize", {
            "INPUT": slic_raster, "BAND": 1, "FIELD": "tile_id",
            "EIGHT_CONNECTEDNESS": False, "OUTPUT": parameters[self.OUTPUT],
        }, context=context, feedback=feedback, is_child_algorithm=True)
        return {self.OUTPUT: poly["OUTPUT"]}

    def _run_addon(self, parameters, context, feedback):
        addon_id = next((alg for alg in ("grass7:i.superpixels.slic", "grass:i.superpixels.slic")
                         if QgsApplication.processingRegistry().algorithmById(alg)), None)
        if addon_id is None:
            raise QgsProcessingException(
                "The GRASS i.superpixels.slic addon is unavailable in QGIS Processing. "
                "Supply a categorical SLIC labels raster made with the S10 R/supercells "
                "workflow, or install and expose the addon to the GRASS provider."
            )
        layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        radius = self.parameterAsDouble(parameters, self.RADIUS, context)
        compactness = self.parameterAsDouble(parameters, self.COMPACTNESS, context)

        if layer is None or layer.crs().mapUnits() != Qgis.DistanceUnit.Meters:
            raise QgsProcessingException("Proxy raster must use a projected CRS with meter units.")
        px = layer.rasterUnitsPerPixelX()
        py = layer.rasterUnitsPerPixelY()
        pixel_area = abs(px * py)
        if pixel_area <= 0:
            raise QgsProcessingException("Invalid raster cell size.")
        ncells = layer.width() * layer.height()
        raster_area = ncells * pixel_area
        recorder_area = math.pi * (radius ** 2)
        k = max(1, int(round(raster_area / recorder_area)))
        feedback.pushInfo(
            f"Raster area = {raster_area:.0f} m^2 | recorder area = {recorder_area:.0f} m^2 | "
            f"estimated superpixels k = {k}"
        )

        # Parameter keys below follow the i.superpixels.slic addon manual.
        # Verify against your build via "Copy as Python command" if it errors.
        slic = processing.run(
            addon_id,
            {
                "input": [parameters[self.INPUT]],
                "num_pixels": k,
                "compactness": compactness,
                "output": "TEMPORARY_OUTPUT",
                "GRASS_REGION_PARAMETER": None,
                "GRASS_REGION_CELLSIZE_PARAMETER": 0,
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        slic_raster = slic.get("output")
        if slic_raster is None:
            raise QgsProcessingException("i.superpixels.slic returned no 'output' raster.")
        return slic_raster

    def name(self):
        return "slic_tessellation"

    def displayName(self):
        return "STEP III (b) - Tessellation: SLIC superpixels"

    def group(self):
        return "Workflow steps"

    def groupId(self):
        return "workflow"

    def shortHelpString(self):
        return (
            "Segments the landscape proxy into SLIC superpixels using the GRASS addon "
            "i.superpixels.slic (replacing the R 'supercells' step). The number of "
            "superpixels is estimated from raster area / recorder area. The result is "
            "polygonized into vector tiles. Requires a categorical SLIC labels raster or the GRASS addon exposed in Processing. "
            "The GRASS output is not identical to S10 R/supercells. See README for citation."
        ) + CITATION

    def createInstance(self):
        return SlicTessellationAlgorithm()
