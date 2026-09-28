"""Human-readable names for temporary Processing outputs."""

from qgis.core import QgsProcessingContext


def name_output(parameters, output_key, destination, name, context):
    requested = parameters.get(output_key)
    if context.willLoadLayerOnCompletion(destination):
        context.layerToLoadOnCompletionDetails(destination).name = name
    elif requested in (None, "TEMPORARY_OUTPUT"):
        context.addLayerToLoadOnCompletion(
            destination, QgsProcessingContext.LayerDetails(name, context.project(), output_key))
