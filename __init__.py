"""Ecoacoustic Spatial Sampling - QGIS Processing plugin.

Entry point. QGIS calls classFactory(iface) to instantiate the plugin.
"""


def classFactory(iface):  # noqa: N802 (QGIS-required name)
    from .plugin import EcoacousticSamplingPlugin
    return EcoacousticSamplingPlugin(iface)
