import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlretrieve

import requests


def main():
    bbox = (-124.057946, 46.315697, -117.916931, 48.588924)
    download_dir = '../data/raw'
    downloader = Download(bbox, download_dir)
    downloader.download()
    with open('paths.json', 'w') as f:
        json.dump(downloader.paths, f)


class Download(object):
    """docstring for Download"""
    def __init__(self, bbox, data_dir):
        super(Download, self).__init__()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True, parents=True)

        self.bbox = bbox
        self.api = NationalMapAPI()

    def download(self):
        """Download all necessary files
        """
        # National Boundary Dataset
        self.nbd_paths = self._download_product(
            product='nbd', extent='State', fmt='FileGDB 10.1')

        # DEM
        self.dem_paths = self._download_product(
            product='ned1', extent='1 x 1 degree', fmt='IMG')

        # Contours
        self.contour_paths = self._download_product(
            product='ned1/3_contours',
            extent='1 x 1 degree',
            fmt='FileGDB 10.1')

        # NHD
        self.nhd_paths = self._download_product(
            product='nhd', extent='HU-8 Subbasin', fmt='FileGDB 10.1')

        # GNIS
        self.gnis_paths = self._download_product(
            product='gnis', extent='State', fmt='TXT (pipes)')

        # Small-scale datasets
        self.sm_bound_paths = self._download_product(
            product='sm_bound', extent='National', fmt='FileGDB 10.1')
        self.sm_contour_paths = self._download_product(
            product='sm_contour', extent='National', fmt='FileGDB 10.1')
        self.sm_hydro_paths = self._download_product(
            product='sm_hydro', extent='National', fmt='FileGDB 10.1')
        self.sm_trans_paths = self._download_product(
            product='sm_trans', extent='National', fmt='FileGDB 10.1')

        # Structures dataset
        self.nsd_paths = self._download_product(
            product='nsd', extent='State', fmt='FileGDB 10.1')

        # National Transportation Dataset
        self.ntd_paths = self._download_product(
            product='ntd', extent='State', fmt='FileGDB 10.1')

        # Woodland areas
        self.woodland_paths = self._download_product(
            product='woodland', extent='State', fmt='FileGDB 10.1')

        # Topo Map Vector
        # This is combined vector data for a 7.5x7.5 degree grid, essentially
        # what I'm creating above. However, from the documentation sheet,
        # section 3
        # https://viewer.nationalmap.gov/tools/topotemplate/contents/TopoTNMStyleTemplateFAQ.pdf
        # > TNM Derived Names is a filtered and enriched dataset
        # > intended specifically to be used in the Topo TNM Style Template for
        # > symbolizing and labeling named features. TNM Derived Names data are
        # > provided only in conjunction with Topo Map Vector Data products and
        # > due to the filtering process does not include all GNIS names
        # > available in the standard GNIS dataset.
        # So I'll use the combined vector files just to extract the derived
        # names, instead of using all the GNIS names
        self.combined_vector = self._download_product(
            product='Combined Vector',
            extent='7.5 x 7.5 minute',
            fmt='FileGDB 10.1')

    def _download_product(self, product, extent, fmt):
        """Find products intersecting bbox and download them

        TODO: Use requests.session for multiple URLs
        """
        results = self.api.search_products(
            self.bbox, product=product, extent=extent, fmt=fmt)
        local_paths = []
        for result in results:
            local_path = download_url(result['downloadURL'], self.data_dir)
            local_paths.append(local_path)

        return local_paths

    @property
    def paths(self):
        paths = {
            'nbd': _paths_to_str(self.nbd_paths),
            'nhd': _paths_to_str(self.nhd_paths),
            'contours': _paths_to_str(self.contour_paths),
            'ned1': _paths_to_str(self.dem_paths),
            'gnis': _paths_to_str(self.gnis_paths),
            'sm_bound': _paths_to_str(self.sm_bound_paths),
            'sm_contour': _paths_to_str(self.sm_contour_paths),
            'sm_hydro': _paths_to_str(self.sm_hydro_paths),
            'sm_trans': _paths_to_str(self.sm_trans_paths),
            'nsd': _paths_to_str(self.nsd_paths),
            'ntd': _paths_to_str(self.ntd_paths),
            'woodland': _paths_to_str(self.woodland_paths),
            'combined_vector': _paths_to_str(self.combined_vector)}
        return paths


class NationalMapAPI:
    """Wrapper for National Map API

    Written documentation:
    https://viewer.nationalmap.gov/help/documents/TNMAccessAPIDocumentation/TNMAccessAPIDocumentation.pdf

    Playground:
    https://viewer.nationalmap.gov/tnmaccess/api/index
    """
    def __init__(self):
        super(NationalMapAPI, self).__init__()
        self.baseurl = 'https://viewer.nationalmap.gov/tnmaccess/api'

    def search_products(self, bbox, product, extent, fmt):
        """Search the products endpoint of the National Map API

        Args:
            - bbox: (left, bottom, right, top)
            - product: short name of product
            - extent: geographic size of results, i.e. national, state, 1x1 grid, etc.
        """
        url = f'{self.baseurl}/products'

        products_xw = {
            'nbd':
                'National Boundary Dataset (NBD)',
            'nhd':
                'National Hydrography Dataset (NHD) Best Resolution',
            'wbd':
                'National Watershed Boundary Dataset (WBD)',
            'naip':
                'USDA National Agriculture Imagery Program (NAIP)',
            'ned1/3':
                'National Elevation Dataset (NED) 1/3 arc-second',
            'ned1/3_contours':
                'National Elevation Dataset (NED) 1/3 arc-second - Contours',
            'ned1':
                'National Elevation Dataset (NED) 1 arc-second',
            'gnis':
                'National Geographic Names Information System (GNIS)',
            'sm_bound':
                'Small-scale Datasets - Boundaries',
            'sm_contour':
                'Small-scale Datasets - Contours',
            'sm_hydro':
                'Small-scale Datasets - Hydrography',
            'sm_trans':
                'Small-scale Datasets - Transportation',
            'nsd':
                'National Structures Dataset (NSD)',
            'ntd':
                'National Transportation Dataset (NTD)',
            'woodland':
                'Land Cover - Woodland',
            'Combined Vector':
                'Combined Vector'}
        product_kw = products_xw.get(product)
        if product_kw is None:
            msg = 'Invalid product_name provided'
            msg += f"\nValid values: {', '.join(products_xw.keys())}"
            raise ValueError(msg)

        valid_extents = {
            '1 x 1 degree', '1 x 2 degree', '1 x 3 degree', '1 x 4 degree',
            '15 x 15 minute', '2 x 1 degree', '3.75 x 3.75 minute',
            '30 x 30 minute', '30 x 60 minute', '7.5 x 15 minute',
            '7.5 x 7.5 minute', 'Contiguous US', 'HU-2 Region',
            'HU-4 Subregion', 'HU-8 Subbasin', 'National', 'North America',
            'State', 'Varies'}
        if extent not in valid_extents:
            msg = 'Invalid extent provided'
            msg += f"\nValid values: {valid_extents}"
            raise ValueError(msg)

        valid_formats = {
            'ArcExport', 'ArcGrid', 'BIL', 'FileGDB 10.1', 'GeoPDF', 'GeoTIFF',
            'GridFloat', 'IMG', 'JPEG2000', 'LAS,LAZ', 'Shapefile', 'TIFF',
            'TXT (pipes)'}
        if fmt not in valid_formats:
            msg = 'Invalid format provided'
            msg += f"\nValid values: {valid_formats}"
            raise ValueError(msg)

        params = {
            'datasets': product_kw,
            'bbox': ','.join(map(str, bbox)),
            'outputFormat': 'JSON',
            'version': 1,
            'prodExtents': extent,
            'prodFormats': fmt}

        res = requests.get(url, params=params)
        res = res.json()
        # If I don't need to page for more results, return
        if len(res['items']) == res['total']:
            return [x for x in res['items'] if x['bestFitIndex'] > 0]

        # Otherwise, need to page
        all_results = [*res['items']]
        n_retrieved = len(res['items'])
        n_total = res['total']

        for offset in range(n_retrieved, n_total, n_retrieved):
            params['offset'] = offset
            res = requests.get(url, params=params).json()
            all_results.extend(res['items'])

        # Keep all results with best fit index >0
        return [x for x in all_results if x['bestFitIndex'] > 0]


def download_url(url, directory, overwrite=False):
    # Cache original download in self.raw_dir
    parsed_url = urlparse(url)
    filename = Path(parsed_url.path).name
    local_path = Path(directory) / filename
    if overwrite or (not local_path.exists()):
        urlretrieve(url, local_path)

    return local_path.resolve()


def _paths_to_str(paths):
    return [str(path) for path in paths]


if __name__ == '__main__':
    main()
