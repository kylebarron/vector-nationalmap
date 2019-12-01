import json
import os
import tempfile
from pathlib import Path
from zipfile import ZipFile

import fiona
import geopandas as gpd
import pandas as pd
from osgeo import gdal
from pyproj.exceptions import CRSError


def main():
    out_dir = Path('../data/cleaned')
    out_dir.mkdir(exist_ok=True, parents=True)

    with open('paths.json') as f:
        data_paths = json.load(f)

    # Layer name: [columns to keep]
    keep_cols_dict = {
        'GU_CountyOrEquivalent': None,
        'GU_IncorporatedPlace': None,
        'GU_StateOrTerritory': None,
        'GU_MinorCivilDivision': None,
        'GU_Reserve': None,
        'GU_NativeAmericanArea': None,
        'GU_Jurisdictional': None,
        'GU_UnincorporatedPlace': None,
        'GU_PLSSFirstDivision': None,
        'GU_PLSSSpecialSurvey': None,
        'GU_PLSSTownship': None}

    make_hillshade(data_paths['ned1'])

    # Extract National Boundaries Dataset
    extract_layers(
        paths=data_paths['nbd'], out_dir=out_dir, keep_cols_dict=keep_cols_dict)

    # Extract National Hydrography Dataset
    keep_layers = [
        'NHDArea', 'NHDFlowline', 'NHDLine', 'NHDPoint', 'NHDWaterbody']
    extract_layers(
        paths=data_paths['nhd'],
        out_dir=out_dir,
        keep_layers=keep_layers,
        keep_cols_dict=keep_cols_dict)

    # Extract contours
    extract_layers(
        paths=data_paths['contours'],
        out_dir=out_dir,
        keep_cols_dict=keep_cols_dict)

    data_paths.keys()


def extract_layers(
        paths, out_dir, keep_layers=None, keep_cols_dict={}, overwrite=False):
    """Extract layers from type of files

    Args:
        - paths: Paths to files that have identical layers
        - out_dir: directory to save merged geometry datasets
    """
    layers = flatten_list([fiona.listlayers(path) for path in paths])
    layers = sorted(list(set(layers)))

    if keep_layers is not None:
        layers = [l for l in layers if l in keep_layers]

    geojson_paths = []
    for layer in layers:
        out_path = Path(out_dir) / (layer + '.geojson')

        if (not overwrite) and out_path.exists():
            geojson_paths.append(out_path)
            continue

        try:
            gdfs = [
                gpd.read_file(f, layer=layer).to_crs(epsg=4326) for f in paths]
        except CRSError:
            print(f'Warning: CRSError on layer: {layer}. Attr only dataset?')
            continue

        gdf = gpd.GeoDataFrame(pd.concat(gdfs))

        # Keep only necessary columns
        keep_cols = keep_cols_dict.get(layer)
        if keep_cols is not None:
            keep_cols.append(gdf.geometry.name)
            gdf = gdf[keep_cols]

        # Don't try to write empty datset
        if len(gdf) == 0:
            continue

        # Write to newline-delimited geojson!!
        # Makes Tippecanoe parsing much, much faster
        gdf.to_file(out_path, driver='GeoJSONSeq')
        geojson_paths.append(out_path)
        print(f'Extracted layer: {layer}')

    return geojson_paths


def make_hillshade(dem_paths):
    # Make sure all dem_paths exist
    # An obscure error is given if the files don't exist
    for dem_path in dem_paths:
        if not Path(dem_path).exists():
            raise FileNotFoundError(dem_path)

    tmpdir = tempfile.mkdtemp()
    # Extract each dem_path into tmpdir
    unzipped_paths = []
    for dem_path in dem_paths:
        zf = ZipFile(dem_path)
        names = zf.namelist()
        img_file = [x for x in names if x.endswith('.img')]
        assert len(img_file) == 1, 'More than one img file in zip file'
        img_file = img_file[0]

        unzipped_path = Path(tmpdir) / img_file
        with open(unzipped_path, 'wb') as f:
            f.write(zf.read(img_file))

        unzipped_paths.append(unzipped_path)

    vrt_path = os.path.join(tmpdir, 'dem.vrt')

    # Setting vrt to None is weird but required
    # https://gis.stackexchange.com/a/314580
    # https://gdal.org/tutorials/raster_api_tut.html#using-createcopy
    vrt = gdal.BuildVRT(vrt_path, unzipped_paths)
    vrt = None

    # Check that vrt_path actually was created
    if not Path(vrt_path).exists():
        raise ValueError('Unable to create virtual raster')

    return vrt_path

    dem_paths

    pass


def flatten_list(l):
    return [item for sublist in l for item in sublist]


if __name__ == '__main__':
    main()
