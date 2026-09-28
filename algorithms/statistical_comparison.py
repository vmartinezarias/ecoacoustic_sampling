"""STEP VI - Statistical comparison: KS test + 1D Wasserstein distance.

Notebook equivalent: the R block (tidyverse/ggpubr) computing ks.test and a
Wasserstein-like distance per method. Ported to pure numpy so no R is needed.

Input: a complete reference layer and multiple subsample layers, each with a
'L_proxy_mean' field. A pre-merged Origin-labelled layer remains supported.

Output: a geometry-less table with, per method, the KS statistic, KS p-value
(asymptotic) and the 1D Wasserstein distance vs the reference distribution.
"""

from ..citation import CITATION

import numpy as np
from qgis.core import (
    Qgis,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterString,
    QgsProcessingParameterFeatureSink,
    QgsFields,
    QgsField,
    QgsFeature,
    QgsProcessingException,
)
from qgis.PyQt.QtCore import QMetaType  # QGIS 4 / Qt6: field types use QMetaType, not QVariant


def _ks_2samp(a, b):
    """Two-sample KS statistic and asymptotic p-value (numpy only)."""
    a = np.sort(np.asarray(a, dtype=float))
    b = np.sort(np.asarray(b, dtype=float))
    grid = np.concatenate([a, b])
    cdf_a = np.searchsorted(a, grid, side="right") / a.size
    cdf_b = np.searchsorted(b, grid, side="right") / b.size
    d = float(np.max(np.abs(cdf_a - cdf_b)))
    if d == 0.0:
        return 0.0, 1.0
    n, m = a.size, b.size
    en = n * m / (n + m)
    lam = (np.sqrt(en) + 0.12 + 0.11 / np.sqrt(en)) * d
    j = np.arange(1, 101)
    p = 2.0 * np.sum(((-1.0) ** (j - 1)) * np.exp(-2.0 * (lam ** 2) * (j ** 2)))
    p = float(min(1.0, max(0.0, p)))
    return d, p


def _wasserstein1(a, b):
    """1D Wasserstein-1 distance = integral of |CDF_a - CDF_b| (numpy only)."""
    a = np.sort(np.asarray(a, dtype=float))
    b = np.sort(np.asarray(b, dtype=float))
    grid = np.sort(np.concatenate([a, b]))
    deltas = np.diff(grid)
    cdf_a = np.searchsorted(a, grid[:-1], side="right") / a.size
    cdf_b = np.searchsorted(b, grid[:-1], side="right") / b.size
    return float(np.sum(np.abs(cdf_a - cdf_b) * deltas))


class StatisticalComparisonAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    REFERENCE_LAYER = "REFERENCE_LAYER"
    SUBSAMPLE_LAYERS = "SUBSAMPLE_LAYERS"
    VALUE_FIELD = "VALUE_FIELD"
    ORIGIN_FIELD = "ORIGIN_FIELD"
    REFERENCE = "REFERENCE"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.REFERENCE_LAYER, "Complete scenario layer (Step V output)",
            optional=True))
        self.addParameter(QgsProcessingParameterMultipleLayers(
            self.SUBSAMPLE_LAYERS, "Subsample layers (select one or more Step V outputs)",
            layerType=Qgis.ProcessingSourceType.Vector, optional=True))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, "Already merged layer (legacy option)", optional=True))
        self.addParameter(QgsProcessingParameterString(
            self.VALUE_FIELD, "Numeric value field (same name in all layers)",
            defaultValue="L_proxy_mean"))
        self.addParameter(QgsProcessingParameterString(
            self.ORIGIN_FIELD, "Group field for merged layer", defaultValue="Origin"))
        self.addParameter(QgsProcessingParameterString(
            self.REFERENCE, "Reference group in merged layer", defaultValue="complete"))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Comparison table", type=Qgis.ProcessingSourceType.Vector))

    @staticmethod
    def _values(layer, field):
        if layer.fields().indexFromName(field) < 0:
            raise QgsProcessingException(
                f"Field '{field}' is missing from '{layer.sourceName() if hasattr(layer, 'sourceName') else layer.name()}'.")
        values = []
        for feature in layer.getFeatures():
            try:
                value = float(feature[field])
            except (TypeError, ValueError):
                continue
            if np.isfinite(value):
                values.append(value)
        return values

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        complete = self.parameterAsSource(parameters, self.REFERENCE_LAYER, context)
        subsamples = self.parameterAsLayerList(parameters, self.SUBSAMPLE_LAYERS, context)
        value_field = self.parameterAsString(parameters, self.VALUE_FIELD, context)
        origin_field = self.parameterAsString(parameters, self.ORIGIN_FIELD, context)
        reference = self.parameterAsString(parameters, self.REFERENCE, context)

        groups = {}
        if complete is not None or subsamples:
            if complete is None or not subsamples:
                raise QgsProcessingException(
                    "Select a complete layer and at least one subsample layer.")
            if source is not None:
                raise QgsProcessingException(
                    "Use separate layers or the already merged layer, not both.")
            ref_vals = np.asarray(self._values(complete, value_field), dtype=float)
            for layer in subsamples:
                origin_idx = layer.fields().indexFromName(origin_field)
                origins = (set(str(f[origin_field]) for f in layer.getFeatures())
                           if origin_idx >= 0 else set())
                label = next(iter(origins)) if len(origins) == 1 and next(iter(origins)) not in ("", "complete", "None") else layer.name()
                if label in groups:
                    base = label
                    suffix = 2
                    while label in groups:
                        label = f"{base} ({suffix})"
                        suffix += 1
                groups[label] = self._values(layer, value_field)
        else:
            if source is None:
                raise QgsProcessingException(
                    "Select separate complete/subsample layers or an already merged layer.")
            if source.fields().indexFromName(value_field) < 0 or source.fields().indexFromName(origin_field) < 0:
                raise QgsProcessingException("Value or group field is absent from the merged layer.")
            for feature in source.getFeatures():
                try:
                    value = float(feature[value_field])
                except (TypeError, ValueError):
                    continue
                if np.isfinite(value):
                    groups.setdefault(str(feature[origin_field]), []).append(value)
            if reference not in groups:
                raise QgsProcessingException(
                    f"Reference group '{reference}' not found. Found: {sorted(groups)}")
            ref_vals = np.asarray(groups.pop(reference), dtype=float)
        if not ref_vals.size:
            raise QgsProcessingException("The complete scenario contains no valid numeric values.")
        groups = {key: values for key, values in groups.items() if values}
        if not groups:
            raise QgsProcessingException("No subsample contains valid numeric values.")

        out_fields = QgsFields()
        out_fields.append(QgsField("Method", QMetaType.Type.QString))
        out_fields.append(QgsField("N_ref", QMetaType.Type.Int))
        out_fields.append(QgsField("N_sub", QMetaType.Type.Int))
        out_fields.append(QgsField("KS_statistic", QMetaType.Type.Double))
        out_fields.append(QgsField("KS_p_value", QMetaType.Type.Double))
        out_fields.append(QgsField("Wasserstein", QMetaType.Type.Double))
        out_fields.append(QgsField("S10_sorted_delta", QMetaType.Type.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, out_fields, Qgis.WkbType.NoGeometry
        )
        if sink is None:
            raise QgsProcessingException("Could not create comparison table.")

        for method in sorted(groups):
            sub = np.asarray(groups[method], dtype=float)
            if sub.size == 0:
                continue
            d, p = _ks_2samp(ref_vals, sub)
            w = _wasserstein1(ref_vals, sub)
            count = min(len(ref_vals), len(sub))
            legacy = float(np.mean(np.abs(np.sort(ref_vals)[:count] - np.sort(sub)[:count])))
            feedback.pushInfo(
                f"{method}: KS D={d:.4f} p={p:.4g} | Wasserstein={w:.4f}"
            )
            f = QgsFeature(out_fields)
            f.setAttributes([method, int(ref_vals.size), int(sub.size), d, p, w, legacy])
            if not sink.addFeature(f):
                raise QgsProcessingException("Could not write comparison row.")

        return {self.OUTPUT: dest_id}

    def name(self):
        return "statistical_comparison"

    def displayName(self):
        return "STEP VI - Statistical comparison (KS + Wasserstein)"

    def group(self):
        return "Workflow steps"

    def groupId(self):
        return "workflow"

    def shortHelpString(self):
        return (
            "Choose the complete scenario layer and one or more separate subsample "
            "layers; no manual merge is needed. Each layer must have the same numeric "
            "field (default L_proxy_mean). Output Method uses a unique Origin label "
            "when present, otherwise the layer name; duplicate names receive a suffix. The already merged input remains available for old "
            "projects. Compares each subsample's distribution of proxy means against the complete "
            "set using the two-sample Kolmogorov-Smirnov test (statistic + asymptotic "
            "p-value) and the true 1D Wasserstein distance. 'S10_sorted_delta' reproduces the "
            "notebook's truncated sorted-pair statistic, which is not the mathematical "
            "Wasserstein distance when sample sizes differ. KS p-values are asymptotic "
            "and unreliable for small samples or repeated proxy values. Compare KS D "
            "and Wasserstein alongside sampling effort; p > 0.05 does not establish equivalence."
        ) + CITATION

    def createInstance(self):
        return StatisticalComparisonAlgorithm()
