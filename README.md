# MILEVA: Mapping-Informed Landscape Ecotopes for Versatile Acoustic Sampling

![MILEVA icon: flag](icon.svg)  
![Grupo Herpetológico de Antioquia](logo_gha.png)

**Version 0.4.1. Processing plugin for QGIS 4.x.**

**Plugin authors:** Victor M. Martínez-Arias, Carolina Paniagua-Villada, Maria José Guerrero, and Juan Daza.

**Grupo Herpetológico de Antioquia - GHA:** https://grupoherpetologicodeantioquia.org/

MILEVA helps design ecoacoustic subsampling schemes based on a spatial proxy. It implements the cartographic components and a distributional comparison of the published workflow. Acoustic performance assessment, interpolation, and the final scientific decision require additional analyses.

> **Method citation:** Martínez-Arias, V. M., Paniagua-Villada, C., Guerrero, M. J., & Daza, J. M. (2026). A workflow to optimize spatial sampling in ecoacoustic studies. *Landscape Ecology, 41*, article 126. https://doi.org/10.1007/s10980-026-02372-5. See Supplementary Information S10.

## Installation

1. In QGIS 4.x, open **Plugins → Manage and Install Plugins → Install from ZIP** and select `MILEVA_QGIS4.zip`.
2. Enable the plugin and open **Processing Toolbox → MILEVA → Workflow steps**.
3. Enable the **GRASS GIS Processing Provider** for watershed analysis. MILEVA does not run SLIC directly; SLIC polygons generated using the S10 workflow can be imported as input for step IV.

For radii expressed in meters, use rasters and points in a projected CRS with metric units (for example, EPSG:9377 in Colombia). Layers used in step V must share the same CRS. The default radius of 200 m represents the spatial independence scale used in the article, **not** the detection range of an AudioMoth recorder.

## Workflow

| Step | Tool | Input and output | Relationship with S10 |
|---|---|---|---|
| I | Preparation | Define the research question, recording scheme, and spatial proxy outside the plugin. | Research design decision. |
| II | Rescale landscape proxy | Continuous raster → 1 to 100, preserving NoData. | Min–max scaling. |
| III a | Basins / half-basins | Metric proxy → GRASS watersheds → polygons. | `r.watershed`, threshold `int(πr² / pixel area)`. The proxy is interpreted as a surface to be segmented; it does not necessarily represent a DEM. |
| III b | SLIC | Not executed within the plugin. Import external SLIC polygons for step IV. | S10 uses the R package/functionality `supercells`. |
| III/IV | Complete grid + random subsample | Polygons and/or raster → two point layers: `Complete` and `Random`. | Reproducible random selection within a complete sampling scenario. |
| IV | Select sampling points | Polygons and, optionally, recorder locations → selected sampling points. | Center determined using `native:poleofinaccessibility`; when recorder locations are provided, the nearest recorder to each pole is selected and duplicates are removed. S10 approximates the pole using `representative_point()`. |
| V | Buffer + zonal proxy mean | Points and proxy → polygons containing `L_proxy_mean` and `Origin`. | Mean proxy value within a selected radius. Run for `complete` and for each sampling strategy. |
| VI | Statistical comparison | Complete layer + one or more subsample layers → KS/Wasserstein table. | Layers do not need to be merged; the previous merged-input option remains available. |
| VII | Decision | Interpret the table together with cost, number of recorders, and biological objectives. | Scientific interpretation; not automated. |

### Complete and random designs

Select a polygon layer, a raster, or both to define the study area. MILEVA places points from a complete grid inside the polygons and/or within valid raster pixels, excluding the value 999 by default. Define the **Minimum separation** in meters (200 m by default).

The second output is a random subset of the complete set of points. You can define either a fixed sample size or a percentage and provide a reproducible random seed. Because both datasets are derived from the same grid, no pair of points is separated by less than the specified minimum distance.

Random points therefore represent a **subsample of the complete grid**, rather than continuously distributed random locations.

The study area must use a projected CRS with metric units. If both polygon and raster layers are supplied, they must share the same CRS.

Run step V on the `Complete` layer with Origin=`complete` and on the `Random` layer with Origin=`Random`, using the same raster and radius.

In step VI, select the complete output as the reference layer and the outputs of one or more sampling strategies as subsamples. `Method` uses the `Origin` label when it is unique; otherwise, it uses the layer name. Repeated names receive a suffix.

You may also select step V outputs generated from Basins, Halfbasins, or other sampling designs.

The method does not create new physical recorders. Proposed recorder locations must be validated under field conditions.

The output points from step IV preserve `tile_id`, `recorder_id` (the internal ID of the input layer), and `distance_m` (Euclidean distance expressed in the units of the CRS).

The algorithm skips repeated selections of the same recorder. If several tile-to-recorder assignments must explicitly be retained for the same recorder, this situation should be evaluated before deduplication.

Proposed locations may also require field verification regarding accessibility and safety.

### Interpreting the statistical table

- `KS_statistic` represents the distance between the empirical distributions; lower values indicate greater similarity. `KS_p_value` uses an asymptotic approximation. Frequent ties and small samples may limit its validity. A *p*-value > 0.05 **does not demonstrate equivalence**.

- `Wasserstein` is the standard one-dimensional Wasserstein distance, calculated as the integral of the absolute difference between cumulative distribution functions. Lower values indicate greater similarity, expressed in the units of the spatial proxy.

- `S10_sorted_delta` reproduces the formula used in the S10 notebook: the mean absolute difference between the first `min(n,m)` sorted values. When sample sizes differ, it is **not equivalent** to the Wasserstein distance. It is retained to allow comparison with previous results obtained using the S10 notebook.

- The published article also evaluates performance using interpolated acoustic surfaces, sampling effort, efficiency, and spatial error. These analyses are not performed by this plugin.

## Limitations and validation

MILEVA version 0.4.1 has been **tested in QGIS 4.x and the implemented workflow is operational**. Basins and Halfbasins have been successfully executed, the complete-grid and random-subsampling workflow is functional, zonal proxy statistics and statistical comparisons can be generated, and the resulting layers and tables can be used directly within the QGIS Processing environment.

SLIC segmentation is intentionally not executed within the plugin. External SLIC polygons, such as those produced following the S10 workflow, can instead be imported and used in the corresponding sampling step.

Before applying the workflow to a new study area, a short validation run is recommended. Use a small proxy raster in an appropriate projected CRS, such as EPSG:9377 in Colombia; generate the complete and random scenarios; verify the specified point separation and confirm that random points are a subset of the complete grid; calculate proxy means for both datasets; and compare the resulting layers directly using the statistical comparison tool.

Basins and Halfbasins can also be generated to verify that their corresponding outputs and naming conventions are correctly produced.

For new datasets or study areas, reviewing the QGIS Processing log and manually checking a small number of zonal statistics remains good practice before deploying the final sampling design in the field.
