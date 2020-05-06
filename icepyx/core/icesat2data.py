import datetime as dt
import os
import requests
import json
import warnings
import pprint
import time
import geopandas as gpd
import matplotlib.pyplot as plt

from icepyx.core.Earthdata import Earthdata
import icepyx.core.APIformatting as apifmt
import icepyx.core.is2ref as is2ref
import icepyx.core.granules as granules
from icepyx.core.granules import Granules as Granules
#QUESTION: why doesn't from granules import Granules as Granules work, since granules=icepyx.core.granules?
# from icepyx.core.granules import Granules
from icepyx.core.variables import Variables as Variables
import icepyx.core.geospatial as geospatial
import icepyx.core.validate_inputs as val

#DevGoal: update docs throughout to allow for polygon spatial extent
#Note: add files to docstring once implemented
#DevNote: currently this class is not tested
class Icesat2Data():
    """
    ICESat-2 Data object to query, obtain, and perform basic operations on
    available ICESat-2 datasets using temporal and spatial input parameters.
    Allows the easy input and formatting of search parameters to match the
    NASA NSIDC DAAC and (development goal-not yet implemented) conversion to multiple data types.

    Parameters
    ----------
    dataset : string
        ICESat-2 dataset ID, also known as "short name" (e.g. ATL03).
        Available datasets can be found at: https://nsidc.org/data/icesat-2/data-sets
    spatial_extent : list or string
        Spatial extent of interest, provided as a bounding box, list of polygon coordinates, or
        geospatial polygon file.
        Bounding box coordinates should be provided in decimal degrees as
        [lower-left-longitude, lower-left-latitute, upper-right-longitude, upper-right-latitude].
        Polygon coordinates should be provided as coordinate pairs in decimal degrees as
        [(longitude1, latitude1), (longitude2, latitude2), ... (longitude_n,latitude_n), (longitude1,latitude1)]
        or
        [longitude1, latitude1, longitude2, latitude2, ... longitude_n,latitude_n, longitude1,latitude1].
        Your list must contain at least four points, where the first and last are identical.
        DevGoal: adapt code so the polygon is automatically closed if need be
        Geospatial polygon files are entered as strings with the full file path and
        must contain only one polygon with the area of interest.
        Currently supported formats are: kml, shp, and gpkg
    date_range : list of 'YYYY-MM-DD' strings
        Date range of interest, provided as start and end dates, inclusive.
        The required date format is 'YYYY-MM-DD' strings, where
        YYYY = 4 digit year, MM = 2 digit month, DD = 2 digit day.
        Currently, a list of specific dates (rather than a range) is not accepted.
        DevGoal: accept date-time objects, dicts (with 'start_date' and 'end_date' keys, and DOY inputs).
        DevGoal: allow searches with a list of dates, rather than a range.
    start_time : HH:mm:ss, default 00:00:00
        Start time in UTC/Zulu (24 hour clock). If None, use default.
        DevGoal: check for time in date-range date-time object, if that's used for input.
    end_time : HH:mm:ss, default 23:59:59
        End time in UTC/Zulu (24 hour clock). If None, use default.
        DevGoal: check for time in date-range date-time object, if that's used for input.
    version : string, default most recent version
        Dataset version, given as a 3 digit string. If no version is given, the current
        version is used.

    Returns
    -------
    icesat2data object

    See Also
    --------


    Examples
    --------
    Initializing Icesat2Data with a bounding box.
    >>> reg_a_bbox = [-64, 66, -55, 72]
    >>> reg_a_dates = ['2019-02-22','2019-02-28']
    >>> region_a = icepyx.Icesat2Data('ATL06', reg_a_bbox, reg_a_dates)
    >>> region_a
    [show output here after inputting above info and running it]

    Initializing Icesat2Data with a list of polygon vertex coordinate pairs.
    >>> reg_a_poly = [(-64, 66), (-64, 72), (-55, 72), (-55, 66), (-64, 66)]
    >>> reg_a_dates = ['2019-02-22','2019-02-28']
    >>> region_a = icepyx.Icesat2Data('ATL06', reg_a_poly, reg_a_dates)
    >>> region_a
    [show output here after inputting above info and running it]

    Initializing Icesat2Data with a geospatial polygon file.
    >>> aoi = '/User/name/location/aoi.shp'
    >>> reg_a_dates = ['2019-02-22','2019-02-28']
    >>> region_a = icepyx.Icesat2Data('ATL06', aoi, reg_a_dates)
    >>> region_a
    [show output here after inputting above info and running it]

    """


    # ----------------------------------------------------------------------
    # Constructors

    def __init__(
        self,
        dataset = None,
        spatial_extent = None,
        date_range = None,
        start_time = None,
        end_time = None,
        version = None,
        files = None,
    ):

        warnings.filterwarnings("always")
        warnings.warn("Please note: as of 2020-05-05, a major reorganization of the core icepyx code may result in errors produced by now depricated functions. Please see our documentation pages or example notebooks for updates.")
        
        if (dataset is None or spatial_extent is None or date_range is None) and files is None:
            raise ValueError("Please provide the required inputs. Use help([function]) to view the function's documentation")

        if files is not None:
            self._source = 'files'
            # self.file_vars = Variables(self._source)
        else:
            self._source = 'order'
            # self.order_vars = Variables(self._source)
        # self.variables = Variables(self._source)

        self._dset = is2ref._validate_dataset(dataset)

        self.extent_type, self._spat_extent, self._geom_filepath = val.spatial(spatial_extent)

        self._start, self._end = val.temporal(date_range, start_time, end_time)
 
        self._version = val.dset_version(self.latest_version(), version)
        

    # ----------------------------------------------------------------------
    # Properties

    @property
    def dataset(self):
        """
        Return the short name dataset ID string associated with the icesat2data object.

        Examples
        --------
        >>> region_a = icepyx.Icesat2Data('ATL06',[-64, 66, -55, 72],['2019-02-22','2019-02-28'])
        >>> region_a.dataset
        ATL06
        """
        return self._dset

    @property
    def dataset_version(self):
        """
        Return the dataset version of the data object.

        Examples
        --------
        >>> region_a = icepyx.Icesat2Data('ATL06',[-64, 66, -55, 72],['2019-02-22','2019-02-28'])
        >>> region_a.dataset_version
        002

        >>> region_a = icepyx.Icesat2Data('ATL06',[-64, 66, -55, 72],['2019-02-22','2019-02-28'], version='1')
        >>> region_a.dataset_version
        001
        """
        return self._version

    @property
    def spatial_extent(self):
        """
        Return an array showing the spatial extent of the icesat2data object.
        Spatial extent is returned as an input type (which depends on how
        you initially entered your spatial data) followed by the geometry data.
        Bounding box data is [lower-left-longitude, lower-left-latitute, upper-right-longitude, upper-right-latitude].
        Polygon data is [[list of longitudes],[list of corresponding latitudes]].

        Examples
        --------
        >>> region_a = icepyx.Icesat2Data('ATL06',[-64, 66, -55, 72],['2019-02-22','2019-02-28'])
        >>> region_a.spatial_extent
        ['bounding box', [-64, 66, -55, 72]]
        """

        if self.extent_type == 'bounding_box':
            return ['bounding box', self._spat_extent]
        elif self.extent_type == 'polygon':
            return ['polygon', self._spat_extent] #[self._spat_extent[0::2], self._spat_extent[1::2]]]
        else:
            return ['unknown spatial type', None]

    @property
    def dates(self):
        """
        Return an array showing the date range of the icesat2data object.
        Dates are returned as an array containing the start and end datetime objects, inclusive, in that order.

        Examples
        --------
        >>> region_a = icepyx.Icesat2Data('ATL06',[-64, 66, -55, 72],['2019-02-22','2019-02-28'])
        >>> region_a.dates
        ['2019-02-22', '2019-02-28']
        """
        return [self._start.strftime('%Y-%m-%d'), self._end.strftime('%Y-%m-%d')] #could also use self._start.date()

    @property
    def start_time(self):
        """
        Return the start time specified for the start date.

        Examples
        --------
        >>> region_a = icepyx.Icesat2Data('ATL06',[-64, 66, -55, 72],['2019-02-22','2019-02-28'])
        >>> region_a.start_time
        00:00:00

        >>> region_a = icepyx.Icesat2Data('ATL06',[-64, 66, -55, 72],['2019-02-22','2019-02-28'], start_time='12:30:30')
        >>> region_a.start_time
        12:30:30
        """
        return self._start.strftime('%H:%M:%S')

    @property
    def end_time(self):
        """
        Return the end time specified for the end date.

        Examples
        --------
        >>> region_a = icepyx.Icesat2Data('ATL06',[-64, 66, -55, 72],['2019-02-22','2019-02-28'])
        >>> region_a.end_time
        23:59:59

        >>> region_a = icepyx.Icesat2Data('ATL06',[-64, 66, -55, 72],['2019-02-22','2019-02-28'], end_time='10:20:20')
        >>> region_a.end_time
        10:20:20
        """
        return self._end.strftime('%H:%M:%S')

    @property
    def CMRparams(self):
        """
        Display the CMR key:value pairs that will be submitted. It generates the dictionary if it does not already exist.
        """

        if not hasattr(self, '_CMRparams'): 
            self._CMRparams = apifmt.Parameters('CMR')
        # print(self._CMRparams)
        # print(self._CMRparams.fmted_keys)

        if self._CMRparams.fmted_keys == {}:
            self._CMRparams.build_params(dataset=self.dataset, version=self._version,\
                    start=self._start, end=self._end, extent_type=self.extent_type, spatial_extent=self._spat_extent)

        return self._CMRparams.fmted_keys

    #DevGoal: make sure that if the user updates page size, page num is updated so that all granules would be ordered...
    @property
    def reqparams(self):
        """
        Display the required key:value pairs that will be submitted. It generates the dictionary if it does not already exist.
        """

        if not hasattr(self, '_reqparams'):
            self._reqparams = apifmt.Parameters('required', reqtype='search')
            self._reqparams.build_params()
              
        return self._reqparams.fmted_keys

    @property
    def subsetparams(self, **kwargs):
        """
        Display the subsetting key:value pairs that will be submitted. It generates the dictionary if it does not already exist
        and returns an empty dictionary if subsetting is set to False during ordering.

        See Also
        --------
        order_granules
        """
        if not hasattr(self, '_subsetparams'): self._subsetparams = apifmt.Parameters('subset')
        
        if self._subsetparams==None:
            return {}
        else:
            if self._geom_filepath is not None:
                self._subsetparams.build_params(geom_filepath = self._geom_filepath, \
                                    start=self._start, end=self._end, extent_type=self.extent_type, \
                                    spatial_extent=self._spat_extent, **kwargs)
            else:
                self._subsetparams.build_params(start=self._start, end=self._end,\
                            extent_type=self.extent_type, spatial_extent=self._spat_extent, **kwargs)

            return self._subsetparams.fmted_keys
    
    #DevGoal: add to tests
    #DevGoal: add statements to the following vars properties to let the user know if they've got a mismatched source and vars type
    @property
    def order_vars(self):
        """
        Return the order variables object. 
        This instance is generated when data is ordered from the NSIDC.

        See Also
        --------
        variables.Variables

        Examples
        --------
        >>> region_a = icepyx.Icesat2Data('ATL06',[-64, 66, -55, 72],['2019-02-22','2019-02-28'])
        >>> region_a.earthdata_login(user_id,user_email)
        >>> region_a.order_granules()
        >>> region_a.order_vars
        """
        
        if not hasattr(self, '_order_vars'):
            if self._source == 'order':
                #DevGoal: check for active session here
                if hasattr(self, '_cust_options'):
                    self._order_vars = Variables(self._source, session=self._session, dataset=self.dataset, avail=self._cust_options['variables'])
                else:
                    self._order_vars = Variables(self._source, session=self._session, dataset=self.dataset, version=self._version)

        return self._order_vars


    @property
    def file_vars(self):
        """
        Return the file variables object.
        This instance is generated when files are used to create the data object (not yet implemented).

        See Also
        --------
        variables.Variables

        Examples
        --------
        >>> region_a = icepyx.Icesat2Data('ATL06',[-64, 66, -55, 72],['2019-02-22','2019-02-28'])
        >>> session = region_a.earthdata_login(user_id,user_email)
        >>> region_a.order_granules(session)
        >>> region_a.variables
        """
        
        if not hasattr(self, '_file_vars'):
            if self._source == 'file':
                self._file_vars = Variables(self._source, dataset=self.dataset)

        return self._file_vars

    @property
    def granules(self):
        """
        Return the granules object, which provides the underlying funtionality for searching, ordering,
        and downloading granules for the specified dataset. Users are encouraged to use the built in wrappers
        rather than trying to access the granules object themselves.

        See Also
        --------
        avail_granules
        order_granules
        download_granules
        granules.Granules

        Examples
        --------
        >>>
        """

        if not hasattr(self, '_granules'):
            self._granules = Granules()
        elif self._granules==None:
            self._granules = Granules()
        
        return self._granules


    # ----------------------------------------------------------------------
    # Methods - Get and display neatly information at the dataset level

    def dataset_summary_info(self):
        """
        Display a summary of selected metadata for the specified version of the dataset 
        of interest (the collection).
        """
        if not hasattr(self, '_about_dataset'): self._about_dataset=is2data(self._dset)
        summ_keys = ['dataset_id', 'short_name', 'version_id', 'time_start', 'coordinate_system', 'summary', 'orbit_parameters']
        for key in summ_keys:
            print(key,': ',self._about_dataset['feed']['entry'][int(self._version)-1][key])

    def dataset_all_info(self):
        """
        Display all metadata about the dataset of interest (the collection).
        """
        if not hasattr(self, '_about_dataset'): self._about_dataset=is2data(self._dset)
        pprint.pprint(self._about_dataset)

    def latest_version(self):
        """
        Determine the most recent version available for the given dataset.
        """
        if not hasattr(self, '_about_dataset'): self._about_dataset=is2ref.about_dataset(self._dset)
        return max([entry['version_id'] for entry in self._about_dataset['feed']['entry']])

    def show_custom_options(self, dictview=False):
        """
        Display customization/subsetting options available for this dataset.
        
        Parameters
        ----------
        dictview : boolean, default False
            Show the variable portion of the custom options list as a dictionary with key:value
            pairs representing variable:paths-to-variable rather than as a long list of full
            variable paths.
        
        """
        headers=['Subsetting options', 'Data File Formats (Reformatting Options)', 'Reprojection Options',
                 'Data File (Reformatting) Options Supporting Reprojection',
                 'Data File (Reformatting) Options NOT Supporting Reprojection',
                 'Data Variables (also Subsettable)']
        keys=['options', 'fileformats', 'reprojectionONLY', 'formatreproj', 'noproj', 'variables']

        try:
            all(key in self._cust_options.keys() for key in keys)
        except AttributeError or KeyError:
            self._cust_options=is2ref._get_custom_options(self._session, self.dataset, self._version)

        for h,k in zip(headers,keys):
            print(h)
            if k=='variables' and dictview:
                vgrp,paths = Variables._parse_var_list(self._cust_options[k])
                pprint.pprint(vgrp)
            else:
                pprint.pprint(self._cust_options[k])

  

    # ----------------------------------------------------------------------
    # Methods - Login and Granules (NSIDC-API)

    def earthdata_login(self,uid,email):
        """
        Log in to NSIDC EarthData to access data. Generates the needed session and token for most
        data searches and data ordering/download.

        Parameters
        ----------
        uid : string
            Earthdata login user ID
        email : string
            Email address. NSIDC will automatically send you emails about the status of your order.

        See Also
        --------
        Earthdata.Earthdata
        """
    
        capability_url = f'https://n5eil02u.ecs.nsidc.org/egi/capabilities/{self.dataset}.{self._version}.xml'
        self._session = Earthdata(uid,email,capability_url).login()

    #DevGoal: check to make sure the see also bits of the docstrings work properly in RTD
    def avail_granules(self):
        """
        Get a list of available granules for the icesat2data object's parameters.

        """
        
        #REFACTOR: add test to make sure there's a session
        if not hasattr(self, '_granules'): self.granules
        try: return self.granules.avail
        except AttributeError:
            self.granules.get_avail(self.CMRparams,self.reqparams)

        return granules.info(self.granules.avail)

    #DevGoal: display output to indicate number of granules successfully ordered (and number of errors)
    #DevGoal: deal with subset=True for variables now, and make sure that if a variable subset Coverage kwarg is input it's successfully passed through all other functions even if this is the only one run.
    def order_granules(self, verbose=False, subset=True, **kwargs):
        """
        Place an order for the available granules for the icesat2data object.
        
        See Also
        --------
        granules.place_order
        """
        
        if not hasattr(self, 'reqparams'): self.reqparams
        
        if self._reqparams._reqtype == 'search':
            self._reqparams._reqtype = 'download'
            self._reqparams.build_params()

        if subset is False:
            self._subsetparams=None
        elif subset==True and hasattr(self, '_subsetparams') and self._subsetparams==None:
            del self._subsetparams
     
        #REFACTOR: add checks here to see if the granules object has been created, and also if it already has a list of avail granules (if not, need to create one and add session)
        if not hasattr(self, '_granules'): self.granules
        self._granules.place_order(self.CMRparams, self.reqparams, self.subsetparams, verbose, subset, session=self._session, geom_filepath=self._geom_filepath, **kwargs)


    def download_granules(self, path, verbose=False): #, extract=False):
        """
        Downloads the data ordered using order_granules.

        Parameters
        ----------
        path : string
            String with complete path to desired download location.

        See Also
        --------
        granules.download
        """
        """
        extract : boolean, default False
            Unzip the downloaded granules.
        """
     
        # if not os.path.exists(path):
        #     os.mkdir(path)
        # os.chdir(path)

        if not hasattr(self, '_granules'): self.granules
            
        if not hasattr(self._granules, 'orderIDs') or len(self._granules.orderIDs)==0: self.order_granules(verbose)
    
        self._granules.download(verbose, path, session=self._session)
  
   
    #DevGoal: add testing? What do we test, and how, given this is a visualization.
    #DevGoal(long term): modify this to accept additional inputs, etc.
    #DevGoal: move this to it's own module for visualizing, etc.
    #DevGoal: see Amy's data access notebook for a zoomed in map - implement here?
    def visualize_spatial_extent(self): #additional args, basemap, zoom level, cmap, export
        """
        Creates a map displaying the input spatial extent

        Examples
        --------
        >>> icepyx.Icesat2Data('ATL06','path/spatialfile.shp',['2019-02-22','2019-02-28'])
        >>> region_a.visualize_spatial_extent
        """

        world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        f, ax = plt.subplots(1, figsize=(12, 6))
        world.plot(ax=ax, facecolor='lightgray', edgecolor='gray')
        geospatial.geodataframe(self.extent_type,self._spat_extent).plot(ax=ax, color='#FF8C00',alpha = 0.7)
        plt.show()