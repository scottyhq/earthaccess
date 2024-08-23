"""
This module contains functions to convert EarthAccess Results to geopandas GeoDataFrame

Adapted from https://github.com/nasa/EMIT-Data-Resources/blob/4ae938c7478669cd6393a2e6b1646c8776055cf8/python/modules/tutorial_utils.py
"""
from typing import List, Union
import re
# TODO: handle Optional Dependencies / MyPy
from .search import DataGranule
import geopandas as gpd
import shapely


def _flatten_column_names(df: gpd.pd.DataFrame) -> gpd.pd.DataFrame:
    """
    Drop umm prefix and change CamelCase to lower case with underscores:
    umm.RelatedUrls -> _related_urls
    """
    df.columns = [
        re.sub("([A-Z]+)", r"_\1", col.split(".")[-1]).lower() for col in df.columns
    ]
    
    return df


def _get_shapely_object(
    result: DataGranule,
) -> Union[shapely.geometry.base.BaseGeometry, None]:
    """
    Retrieve the coordinates from the umm metadata and convert to a shapely geometry.
    """
    shape = None
    try:
        geo = result["umm"]["SpatialExtent"]["HorizontalSpatialDomain"]["Geometry"]
        keys = geo.keys()
        if "BoundingRectangles" in keys:
            bounding_rectangle = geo["BoundingRectangles"][0]
            # Create bbox tuple
            bbox_coords = (
                bounding_rectangle["WestBoundingCoordinate"],
                bounding_rectangle["SouthBoundingCoordinate"],
                bounding_rectangle["EastBoundingCoordinate"],
                bounding_rectangle["NorthBoundingCoordinate"],
            )
            # Create shapely geometry from bbox
            shape = shapely.geometry.box(*bbox_coords, ccw=True)
        elif "GPolygons" in keys:
            points = geo["GPolygons"][0]["Boundary"]["Points"]
            # Create shapely geometry from polygons
            shape = shapely.geometry.Polygon(
                [[p["Longitude"], p["Latitude"]] for p in points]
            )
        else:
            raise ValueError(
                "Provided result does not contain bounding boxes/polygons or is incompatible."
            )
    except Exception as e:
        pass
    
    return shape


def _list_metadata_fields(results: List[DataGranule]) -> List[str]:
    metadata_fields = list(_flatten_column_names(gpd.pd.json_normalize(results)).columns)
    return metadata_fields


# def _get_asset(series, type='https') -> str:
#     '''
#     Get data url from list of umm related urls per granule
#     '''
#     # NOTE not sure how to get standard browse link
#     mapping = {'https':'GET DATA', 's3':'GET DATA VIA DIRECT ACCESS'}
#     assets = gpd.pd.DataFrame(series._related_urls)
#     url = assets.loc[ assets.Type == mapping[type] , 'URL'].values[0]
    
#     return url


# def _assign_stac_datetimes(df) -> str:
#     '''
#     Use STAC Spec datetime, start_datetime, and end_datetime for column headers
#     instead of _beginning_date_time	_ending_date_time
#     https://github.com/radiantearth/stac-spec/blob/master/item-spec/item-spec.md#datetime
#     '''
#     mapping = {'_beginning_date_time':'start_datetime',
#                '_ending_date_time':'end_datetime'}
#     df.rename(columns=mapping, inplace=True)
#     df['start_datetime'] = gpd.pd.to_datetime(df['start_datetime'])
#     df['end_datetime'] = gpd.pd.to_datetime(df['end_datetime'])
#     # Nominal datetime is midpoint if not already present
    
#     return url


def results_to_geopandas(
    results: List[DataGranule],
    fields: List[str] = [],
) -> gpd.GeoDataFrame:
    """
    Convert the results of an earthaccess search into a geodataframe using some default fields.
    Add additional ones with the fields kwarg.
    """
    default_fields = [
        "size",
        "concept_id",
        "dataset-id",
        "native-id",
        "provider-id",
        "_related_urls",
        "_single_date_time",
        "_beginning_date_time",
        "_ending_date_time",
        "geometry",
    ]

    results_df = gpd.pd.json_normalize(results, errors="ignore")

    results_df = _flatten_column_names(results_df)
    if len(fields) == 0:
        fields = default_fields
    else:
        fields = list(set(fields + default_fields))

    results_df = results_df.drop(
        columns=[col for col in results_df.columns if col not in fields]
    )

    results_df["_related_urls"] = results_df["_related_urls"].apply(
    lambda links: [
        link
        for link in links
        if link["Type"]
        in [
            "GET DATA",
            "GET DATA VIA DIRECT ACCESS",
            "GET RELATED VISUALIZATION",
        ]
    ]
)
    
    geometries = [
        _get_shapely_object(results[index]) for index in results_df.index.to_list()
    ]
    
    gdf = gpd.GeoDataFrame(results_df, geometry=geometries, crs="EPSG:4326")
    
    return gdf