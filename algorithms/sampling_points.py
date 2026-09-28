"""Step IV: tile poles, or nearest existing recorder for each tile."""

from ..citation import CITATION

import processing
from qgis.core import (
    Qgis, QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber, QgsProcessingParameterFeatureSink,
    QgsProcessingException, QgsProcessingUtils, QgsSpatialIndex, QgsFields,
    QgsField, QgsFeature,
)
from qgis.PyQt.QtCore import QMetaType


class SamplingPointsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    CANDIDATES = "CANDIDATES"
    TOLERANCE = "TOLERANCE"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, "Tessellation tiles", types=[Qgis.ProcessingSourceType.VectorPolygon]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.CANDIDATES, "Existing recorder points (optional)",
            types=[Qgis.ProcessingSourceType.VectorPoint], optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.TOLERANCE, "Pole tolerance (map units)",
            type=Qgis.ProcessingNumberParameterType.Double, defaultValue=1.0, minValue=0.01))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Sampling points"))

    def processAlgorithm(self, parameters, context, feedback):
        tiles = self.parameterAsSource(parameters, self.INPUT, context)
        candidates = self.parameterAsSource(parameters, self.CANDIDATES, context)
        if tiles is None:
            raise QgsProcessingException("Select polygon tiles.")
        pole_result = processing.run("native:poleofinaccessibility", {
            "INPUT": parameters[self.INPUT],
            "TOLERANCE": self.parameterAsDouble(parameters, self.TOLERANCE, context),
            "OUTPUT": "TEMPORARY_OUTPUT",
        }, context=context, feedback=feedback, is_child_algorithm=True)["OUTPUT"]
        poles = QgsProcessingUtils.mapLayerFromString(pole_result, context)
        if poles is None:
            raise QgsProcessingException("Could not load pole points.")
        fields = QgsFields()
        fields.append(QgsField("tile_id", QMetaType.Type.QString))
        fields.append(QgsField("recorder_id", QMetaType.Type.QString))
        fields.append(QgsField("distance_m", QMetaType.Type.Double))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context,
                                          fields, Qgis.WkbType.Point, tiles.sourceCrs())
        if sink is None:
            raise QgsProcessingException("Could not create point output.")
        index = None
        by_id = {}
        if candidates is not None:
            if candidates.sourceCrs() != tiles.sourceCrs():
                raise QgsProcessingException("Reproject existing recorder points to the tiles' CRS first.")
            index = QgsSpatialIndex()
            for f in candidates.getFeatures():
                if f.hasGeometry() and not f.geometry().isEmpty():
                    index.addFeature(f)
                    by_id[f.id()] = f
            if not by_id:
                raise QgsProcessingException("No valid recorder point geometries.")
        selected = set()
        for pole in poles.getFeatures():
            if feedback.isCanceled():
                break
            geom = pole.geometry()
            if geom.isNull() or geom.isEmpty():
                continue
            tile_id = str(pole["tile_id"]) if pole.fields().indexFromName("tile_id") >= 0 else str(pole.id())
            recorder_id = ""
            distance = 0.0
            if index is not None:
                nearest = index.nearestNeighbor(geom.asPoint(), 1)
                if not nearest:
                    continue
                candidate = by_id[nearest[0]]
                recorder_id = str(candidate.id())
                distance = geom.distance(candidate.geometry())
                geom = candidate.geometry()
                if candidate.id() in selected:
                    continue  # one physical recorder cannot be selected twice
                selected.add(candidate.id())
            out = QgsFeature(fields)
            out.setGeometry(geom)
            out.setAttributes([tile_id, recorder_id, distance])
            if not sink.addFeature(out):
                raise QgsProcessingException("Could not write sampling point.")
        return {self.OUTPUT: dest}

    def name(self):
        return "sampling_points"

    def displayName(self):
        return "STEP IV - Select sampling points"

    def group(self):
        return "Workflow steps"

    def groupId(self):
        return "workflow"

    def shortHelpString(self):
        return ("Computes the pole of inaccessibility in each tile. With an existing recorder "
                "layer, selects its nearest point for each pole and removes duplicate recorder "
                "selections, as in the published design. Without one, outputs proposed poles. "
                "The distance field is in meters only when the tile CRS uses meters. "
                "The S10 notebook uses representative_point() as an approximation; this "
                "algorithm computes the true pole. See README for citation and limitations.") + CITATION

    def createInstance(self):
        return SamplingPointsAlgorithm()
