"""Step V: buffer points in a meter CRS and extract landscape proxy means."""

from ..citation import CITATION

import processing
from qgis.core import (
    Qgis, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterRasterLayer, QgsProcessingParameterNumber,
    QgsProcessingParameterString, QgsProcessingParameterFeatureSink,
    QgsField, QgsFields, QgsFeature, QgsProcessingException, QgsProcessingUtils,
)
from qgis.PyQt.QtCore import QMetaType


class BufferZonalAlgorithm(QgsProcessingAlgorithm):
    POINTS = "POINTS"
    RASTER = "RASTER"
    RADIUS = "RADIUS"
    ORIGIN = "ORIGIN"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.POINTS, "Sampling points", types=[Qgis.ProcessingSourceType.VectorPoint]))
        self.addParameter(QgsProcessingParameterRasterLayer(self.RASTER, "Landscape proxy raster"))
        self.addParameter(QgsProcessingParameterNumber(
            self.RADIUS, "Buffer radius (meters)",
            type=Qgis.ProcessingNumberParameterType.Double, defaultValue=200.0, minValue=1.0))
        self.addParameter(QgsProcessingParameterString(
            self.ORIGIN, "Origin label (complete or a subsample name)", defaultValue="complete"))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Buffered samples with proxy mean"))

    def processAlgorithm(self, parameters, context, feedback):
        points = self.parameterAsSource(parameters, self.POINTS, context)
        raster = self.parameterAsRasterLayer(parameters, self.RASTER, context)
        if points is None or raster is None:
            raise QgsProcessingException("Select both points and a raster.")
        if points.sourceCrs().mapUnits() != Qgis.DistanceUnit.Meters:
            raise QgsProcessingException("Points must use a projected CRS with meter units.")
        if points.sourceCrs() != raster.crs():
            raise QgsProcessingException("Reproject the proxy raster to the points' CRS first.")
        buffered = processing.run("native:buffer", {
            "INPUT": parameters[self.POINTS],
            "DISTANCE": self.parameterAsDouble(parameters, self.RADIUS, context),
            "SEGMENTS": 16, "DISSOLVE": False, "END_CAP_STYLE": 0, "JOIN_STYLE": 0,
            "OUTPUT": "TEMPORARY_OUTPUT",
        }, context=context, feedback=feedback, is_child_algorithm=True)["OUTPUT"]
        zonal = processing.run("native:zonalstatisticsfb", {
            "INPUT": buffered, "INPUT_RASTER": parameters[self.RASTER],
            "RASTER_BAND": 1, "COLUMN_PREFIX": "mileva_", "STATISTICS": [2],
            "OUTPUT": "TEMPORARY_OUTPUT",
        }, context=context, feedback=feedback, is_child_algorithm=True)["OUTPUT"]
        layer = QgsProcessingUtils.mapLayerFromString(zonal, context)
        if layer is None:
            raise QgsProcessingException("Could not load zonal statistics result.")
        mean_idx = layer.fields().indexFromName("mileva_mean")
        if mean_idx < 0:
            raise QgsProcessingException("Expected 'mileva_mean' was not created by zonal statistics.")
        if layer.fields().indexFromName("L_proxy_mean") >= 0 or layer.fields().indexFromName("Origin") >= 0:
            raise QgsProcessingException("Input already contains 'L_proxy_mean' or 'Origin'.")
        fields = QgsFields(layer.fields())
        fields.append(QgsField("L_proxy_mean", QMetaType.Type.Double))
        fields.append(QgsField("Origin", QMetaType.Type.QString))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context,
                                          fields, layer.wkbType(), layer.crs())
        if sink is None:
            raise QgsProcessingException("Could not create buffered output.")
        origin = self.parameterAsString(parameters, self.ORIGIN, context)
        for feat in layer.getFeatures():
            if feedback.isCanceled():
                break
            out = QgsFeature(fields)
            out.setGeometry(feat.geometry())
            out.setAttributes(feat.attributes() + [feat[mean_idx], origin])
            if not sink.addFeature(out):
                raise QgsProcessingException("Could not write buffered sample.")
        return {self.OUTPUT: dest}

    def name(self):
        return "buffer_zonal"

    def displayName(self):
        return "STEP V - Buffer + zonal proxy mean"

    def group(self):
        return "Workflow steps"

    def groupId(self):
        return "workflow"

    def shortHelpString(self):
        return ("Buffers points in a meter CRS and calculates the mean of band 1 of the "
                "proxy raster for each buffer. Run once with Origin='complete' and once "
                "for each subsample, then merge results for Step VI. The output is buffered "
                "polygons with 'L_proxy_mean' and 'Origin'. Use matching projected CRS. "
                "See README for the published workflow citation.") + CITATION

    def createInstance(self):
        return BufferZonalAlgorithm()
