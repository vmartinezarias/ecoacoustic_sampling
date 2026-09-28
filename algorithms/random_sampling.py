"""Generate a systematic complete design and a reproducible random subset."""

import math
import random

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    Qgis, QgsFeature, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber, QgsProcessingParameterRasterLayer,
    QgsSpatialIndex,
)

from ..citation import CITATION
from ..output_names import name_output


def grid_coordinates(minimum, maximum, spacing):
    """Grid centers, exactly `spacing` apart; a small extent gets one center."""
    if maximum <= minimum:
        return []
    width = maximum - minimum
    if width < spacing:
        return [(minimum + maximum) / 2]
    count = int(math.floor(width / spacing))
    margin = (width - (count - 1) * spacing) / 2
    return [minimum + margin + i * spacing for i in range(count)]


class RandomSamplingAlgorithm(QgsProcessingAlgorithm):
    AREA = "AREA"
    RASTER = "RASTER"
    SPACING = "SPACING"
    EXCLUDE_VALUE = "EXCLUDE_VALUE"
    COUNT = "COUNT"
    PERCENT = "PERCENT"
    SEED = "SEED"
    COMPLETE = "COMPLETE"
    RANDOM = "RANDOM"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.AREA, "Study area polygons (optional)",
            types=[Qgis.ProcessingSourceType.VectorPolygon], optional=True))
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.RASTER, "Study area raster (optional; only valid cells)", optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.EXCLUDE_VALUE, "Additional raster NoData value (default 999)",
            type=Qgis.ProcessingNumberParameterType.Double, defaultValue=999.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.SPACING, "Minimum distance / complete grid spacing (meters)",
            type=Qgis.ProcessingNumberParameterType.Double, defaultValue=200.0, minValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.COUNT, "Random sample size (0 uses percentage)",
            type=Qgis.ProcessingNumberParameterType.Integer, defaultValue=0, minValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            self.PERCENT, "Random sample percentage of complete design",
            type=Qgis.ProcessingNumberParameterType.Double, defaultValue=20.0,
            minValue=0.1, maxValue=100.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.SEED, "Random seed (reproducible)",
            type=Qgis.ProcessingNumberParameterType.Integer, defaultValue=12345))
        self.addParameter(QgsProcessingParameterFeatureSink(self.COMPLETE, "Complete points"))
        self.addParameter(QgsProcessingParameterFeatureSink(self.RANDOM, "Random points"))

    def processAlgorithm(self, parameters, context, feedback):
        area = self.parameterAsSource(parameters, self.AREA, context)
        raster = self.parameterAsRasterLayer(parameters, self.RASTER, context)
        if area is None and raster is None:
            raise QgsProcessingException("Choose at least one study area: polygons or raster.")
        crs = area.sourceCrs() if area is not None else raster.crs()
        if not crs.isValid() or crs.mapUnits() != Qgis.DistanceUnit.Meters:
            raise QgsProcessingException("The study area needs a projected CRS with meter units.")
        if area is not None and raster is not None and area.sourceCrs() != raster.crs():
            raise QgsProcessingException("Reproject the polygon and raster layers to the same CRS.")
        extent = area.sourceExtent() if area is not None else raster.extent()
        spacing = self.parameterAsDouble(parameters, self.SPACING, context)
        exclude_value = self.parameterAsDouble(parameters, self.EXCLUDE_VALUE, context)
        xs = grid_coordinates(extent.xMinimum(), extent.xMaximum(), spacing)
        ys = grid_coordinates(extent.yMinimum(), extent.yMaximum(), spacing)
        if len(xs) * len(ys) > 2000000:
            raise QgsProcessingException("More than two million candidates. Increase spacing or clip the area.")

        polygon_index = None
        polygons = {}
        if area is not None:
            polygon_index = QgsSpatialIndex()
            for feature in area.getFeatures():
                if feature.hasGeometry() and not feature.geometry().isEmpty():
                    polygon_index.addFeature(feature)
                    polygons[feature.id()] = feature.geometry()
            if not polygons:
                raise QgsProcessingException("The study area contains no valid polygon geometries.")

        candidates = []
        for row, y in enumerate(ys):
            if feedback.isCanceled():
                raise QgsProcessingException("Sampling canceled.")
            for x in xs:
                point = QgsPointXY(x, y)
                if polygon_index is not None:
                    geometry = QgsGeometry.fromPointXY(point)
                    if not any(polygons[fid].intersects(geometry)
                               for fid in polygon_index.intersects(geometry.boundingBox())):
                        continue
                if raster is not None:
                    value, valid = raster.dataProvider().sample(point, 1)
                    if not valid or not math.isfinite(value) or value == exclude_value:
                        continue
                candidates.append(point)
            if ys:
                feedback.setProgress(int(75 * (row + 1) / len(ys)))
        if not candidates:
            raise QgsProcessingException("No valid grid points fell inside the study area.")

        desired = self.parameterAsInt(parameters, self.COUNT, context)
        if desired == 0:
            desired = max(1, round(len(candidates) *
                                   self.parameterAsDouble(parameters, self.PERCENT, context) / 100))
        if desired > len(candidates):
            raise QgsProcessingException(
                f"Requested {desired} random points, but the complete design has "
                f"only {len(candidates)} candidates.")
        chosen = set(random.Random(self.parameterAsInt(parameters, self.SEED, context)).sample(
            range(len(candidates)), desired))

        fields = QgsFields()
        fields.append(QgsField("sample_id", QMetaType.Type.Int))
        full_sink, full_dest = self.parameterAsSink(
            parameters, self.COMPLETE, context, fields, Qgis.WkbType.Point, crs)
        random_sink, random_dest = self.parameterAsSink(
            parameters, self.RANDOM, context, fields, Qgis.WkbType.Point, crs)
        if full_sink is None or random_sink is None:
            raise QgsProcessingException("Could not create the point outputs.")
        for i, point in enumerate(candidates):
            feature = QgsFeature(fields)
            feature.setAttributes([i + 1])
            feature.setGeometry(QgsGeometry.fromPointXY(point))
            if not full_sink.addFeature(feature):
                raise QgsProcessingException("Could not write complete point.")
            if i in chosen and not random_sink.addFeature(feature):
                raise QgsProcessingException("Could not write random point.")
        feedback.pushInfo(
            f"Complete design: {len(candidates)} points; random subset: {desired}; "
            f"minimum center distance: {spacing:g} m.")
        name_output(parameters, self.COMPLETE, full_dest, "Complete", context)
        name_output(parameters, self.RANDOM, random_dest, "Random", context)
        return {self.COMPLETE: full_dest, self.RANDOM: random_dest}

    def name(self):
        return "random_sampling"

    def displayName(self):
        return "STEP III/IV - Complete grid + random subsample"

    def group(self):
        return "Workflow steps"

    def groupId(self):
        return "workflow"

    def shortHelpString(self):
        return (
            "Choose a polygon area, a raster, or both. Raster NoData and the additional "
            "value 999 are excluded by default. A regular complete grid is "
            "generated within the polygons and/or valid raster pixels; a seeded random "
            "subset is drawn from that complete grid. Grid spacing gives the minimum "
            "distance between any two point centers in either output (default 200 m). "
            "Choose random sample size directly, or set it to 0 to use a percentage. "
            "The random points are a subset of the complete points, matching the paper's "
            "comparison to an original recorder grid. They are not unconstrained random "
            "locations in continuous space. Set the same buffer radius and distinct Origin "
            "labels in Step V, then compare the resulting layers in Step VI."
        ) + CITATION

    def createInstance(self):
        return RandomSamplingAlgorithm()
