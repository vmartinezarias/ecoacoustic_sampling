"""STEP III (a) - Tessellation: basins / half-basins via GRASS r.watershed.

Notebook equivalent: the grass_session block running r.watershed with a
threshold derived from the recorder radius, then exporting basins/half-basins.

In QGIS we don't need grass_session: QGIS ships GRASS, so we call
'grass7:r.watershed' through Processing. The basin raster is then polygonized
so the downstream steps (poles, buffers) receive vector tiles.

NOTE: GRASS algorithm parameter keys vary slightly between QGIS/GRASS builds.
If the r.watershed call fails, open the algorithm dialog once in QGIS, fill it
manually, and use "Advanced > Copy as Python command" to confirm the exact keys.
"""

from ..citation import CITATION
from ..output_names import name_output

import math

import processing
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterNumber,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingException,
)


class WatershedTessellationAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    RADIUS = "RADIUS"
    UNIT = "UNIT"          # 0 = basins, 1 = half-basins
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
            QgsProcessingParameterEnum(
                self.UNIT, "Tessellation unit",
                options=["Basins", "Half-basins"], defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, "Tessellation tiles")
        )

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        radius = self.parameterAsDouble(parameters, self.RADIUS, context)
        unit = self.parameterAsEnum(parameters, self.UNIT, context)

        if layer is None or layer.crs().mapUnits() != Qgis.DistanceUnit.Meters:
            raise QgsProcessingException("Proxy raster must use a projected CRS with meter units.")
        # Minimum basin area -> threshold in pixels (matches the notebook math).
        px = layer.rasterUnitsPerPixelX()
        py = layer.rasterUnitsPerPixelY()
        pixel_area = abs(px * py)
        if pixel_area <= 0:
            raise QgsProcessingException("Could not determine pixel size of the input raster.")
        min_area_m2 = math.pi * (radius ** 2)
        threshold = max(1, int(min_area_m2 / pixel_area))
        feedback.pushInfo(
            f"Recorder area = {min_area_m2:.1f} m^2 | pixel = {pixel_area:.2f} m^2 | "
            f"r.watershed threshold = {threshold} pixels"
        )

        registry = QgsApplication.processingRegistry()
        grass_id = next((alg for alg in ("grass7:r.watershed", "grass:r.watershed")
                         if registry.algorithmById(alg) is not None), None)
        if grass_id is None:
            raise QgsProcessingException("Enable the GRASS GIS Processing Provider for r.watershed.")
        # Outputs: keep both, pick one for tessellation below.
        ws = processing.run(
            grass_id,
            {
                "elevation": parameters[self.INPUT],
                "threshold": threshold,
                "-b": True,  # beautify flat areas (notebook flags='b')
                "basin": "TEMPORARY_OUTPUT",
                "half_basin": "TEMPORARY_OUTPUT",
                "GRASS_REGION_PARAMETER": None,
                "GRASS_REGION_CELLSIZE_PARAMETER": 0,
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        basin_raster = ws.get("half_basin" if unit == 1 else "basin")
        if basin_raster is None:
            raise QgsProcessingException(
                "r.watershed did not return the expected output. Verify the GRASS "
                "parameter names for your build (see the note at the top of this file)."
            )

        # Polygonize the categorical basin raster into vector tiles.
        poly = processing.run(
            "gdal:polygonize",
            {
                "INPUT": basin_raster,
                "BAND": 1,
                "FIELD": "tile_id",
                "EIGHT_CONNECTEDNESS": False,
                "OUTPUT": parameters[self.OUTPUT],
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )
        destination = poly["OUTPUT"]
        name_output(parameters, self.OUTPUT, destination,
                    "Halfbasins" if unit == 1 else "Basins", context)
        return {self.OUTPUT: destination}

    def name(self):
        return "watershed_tessellation"

    def displayName(self):
        return "STEP III (a) - Tessellation: basins / half-basins"

    def group(self):
        return "Workflow steps"

    def groupId(self):
        return "workflow"

    def shortHelpString(self):
        return (
            "Subdivides the landscape into hydrological units using GRASS r.watershed. "
            "The minimum exterior basin threshold is estimated from the recorder radius (pi * r^2), converted "
            "to a pixel threshold. The selected raster (basins or half-basins) is polygonized "
            "into vector tiles for the next steps."
        ) + CITATION

    def createInstance(self):
        return WatershedTessellationAlgorithm()
