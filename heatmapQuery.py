import json
import os
import string
import copy
import math
import time
from datetime import datetime
from httplib import HTTPSConnection
from httplib import HTTPConnection

def __readUrl(conn, url):
    conn.request('GET', url)
    req = conn.getresponse()
    
    if req.status != 200:
        raise Exception(req.reason)
    
    json_body = req.read()    
    places_json = json.loads(json_body)    
    return places_json

'''
Read a list of Google Places into a dict

  api_key - your api key
  type_str - the type string used in the query. Can be single, like 'cafe', or multiple,
             as in 'cafe|bar'
  lat_lngs - a list of lat,lng tuples. Each location will be queried and added to the
             dict
  radius - the radius about which the lat_lngs to search, in meters. Defaults to 6km

Returns
  a dict in which the keys are the unique id assigned to each place by Google, and the
    values are the dicts read from json.loads.
    
  This function may raise HTTPSExceptions
'''
def radarQueryPlaces(api_key, type_str, lat_lngs, radius = 6000):
    url_template = '/maps/api/place/radarsearch/json?key=%s&location=%s&radius=%g&types=%s'
    
    conn = HTTPSConnection('maps.googleapis.com')
    
    locs_dict = dict()
    
    for lat_lng in lat_lngs:
        lat_lng_str = '%g,%g' % lat_lng
        url = url_template % (api_key, lat_lng_str, radius, type_str)
        
        places_json = __readUrl(conn, url)
        
        curr_locs = {result['id'] : result for result in places_json['results']}
        print 'Found ' + str(len(curr_locs)) + ' places'
        locs_dict = dict(locs_dict.items() + curr_locs.items())
    
    conn.close()
    print 'Returning ' + str(len(locs_dict)) + ' places'
    return locs_dict

def nearbyQueryPlaces(api_key, type_str, lat_lngs, radius = 2000):
    url_template = '/maps/api/place/nearbysearch/json?key=%s&location=%s&radius=%g&types=%s'
    next_url_template = '/maps/api/place/nearbysearch/json?key=%s&pagetoken=%s'
    conn = HTTPSConnection('maps.googleapis.com')
    
    locs_dict = dict()
    
    for lat_lng in lat_lngs:
        count = 0
        lat_lng_str = '%g,%g' % lat_lng
        url = url_template % (api_key, lat_lng_str, radius, type_str)
        
        places_json = __readUrl(conn, url)
        
        curr_locs = {result['id'] : result for result in places_json['results']}
        locs_dict = dict(locs_dict.items() + curr_locs.items())
        count = len(curr_locs)

        while places_json.has_key('next_page_token'):
            next_token = places_json['next_page_token']
            url = next_url_template % (api_key, next_token)
            
            time.sleep(0.5)
            places_json = __readUrl(conn, url)
            
            while places_json['status'] == 'INVALID_REQUEST':
                time.sleep(0.5)
                places_json = __readUrl(conn, url)
            
            curr_locs = {result['id'] : result for result in places_json['results']}            
            locs_dict = dict(locs_dict.items() + curr_locs.items())
            
            count += len(curr_locs)

        print 'Found ' + str(count) + ' places'
    
    conn.close()
    
    print 'Returning ' + str(len(locs_dict)) + ' places'
    return locs_dict

def resultsToLocations(result_dict):
    return {result['id'] : (result['geometry']['location']['lat'],
             result['geometry']['location']['lng'])
             for result in result_dict.values()}

'''
A helper function to generate a javascript variable declaration for text replacement.

  var - the variable name to declare
  locs - a dict in which the values are lat,lng tuples
  
Returns
  a string that when run in javascript, will declare the requested variable.

'''
def __generatePlacesDeclaration(var, locs):
    declaration = var + ' = [\n'
    for latlng in locs.values():
        declaration = declaration + '  new google.maps.LatLng(%g, %g),\n' % latlng
    declaration = declaration + '];'
    return declaration

def __generateViewDeclaration(var, locs):
    view_latlng = [0.0, 0.0]
    for latlng in locs.values():
        view_latlng[0] += latlng[0]
        view_latlng[1] += latlng[1]
    view_latlng[0] /= len(locs)
    view_latlng[1] /= len(locs)
    view_latlng = tuple(view_latlng)
    return var + ' = new google.maps.LatLng(%g, %g);' % view_latlng

'''
Create a bunch of html files for your heatmap(s)

  api_key - your api key
  city_name - the name of the city/region to query. This is only used to create subdirectories
  type_strs - a list of type strings used in the query. Can be single, like 'cafe', or multiple,
             as in 'cafe|bar'
  lat_lngs - a list of lat,lng tuples. Each location will be queried and added to the
             dict
  template_html - the template file to use. It is expect to have a line consisting of
                  $place_data$, which will be replaced with a javascript declaration
  radius - the radius about which the lat_lngs to search, in meters. Defaults to 6km

For example, calling:
generateHeatmapHTML('omgwtfbbq', 'Atlanta', ['bar', 'cafe'],
    [(xyz.abc, foo.bar), (one.two, three.four)])

will result in an error because that is not a valid api key, and those locations don't exist,
but if you replace them with parameters that actually work, you'll have two files:

Atlanta/bar.html
Atlanta/cafe.html

When you load these files in a browser, you'll get some nice heatmaps over an embedded google map
    
  This function may raise HTTPSExceptions
'''
def generateHeatmapHTML(city_name, type_str, results, template = 'heatmap.template'):
    
    f_template = open(template, 'r')
    template_str = string.Template(f_template.read())
    f_template.close()
    
    if not os.path.exists(city_name):
        os.makedirs(city_name)
    
    html_name = city_name + '/' + type_str.replace('|', '_or_') + '.html'
    f_html = open(html_name, 'w')
    
    locs = resultsToLocations(results)
    places_declaration = __generatePlacesDeclaration('placeData', locs)
    view_declaration = __generateViewDeclaration('viewCenter', locs)
    
    html_str = copy.copy(template_str)
    
    f_html.write(html_str.substitute(place_data = places_declaration,
                                     view_data = view_declaration))
    f_html.close()

'''
Find the SouthWest/NorthEast limits of the approximate bounding box around a city
This function works by querying the geocode api, supplying city_name for the address.
In order for it to work properly, your city must come up as the first result of the
query.

  city_name - the name of the city in question
    
Returns
  (sw, ne), where sw is the SouthWest boundary returned by geocode, and
            ne is the NorthEast
'''
def queryCityBounds(city_name):
    url = '/maps/api/geocode/json?address=' + city_name + '&sensor=false'
    conn = HTTPConnection('maps.googleapis.com')
    conn.request('GET', url)
    res = conn.getresponse()
    
    if res.status is not 200:
        raise Exception(res.reason)
    
    bound_json = json.loads(res.read())
    
    results = bound_json['results']
    
    if len(results) < 1:
        raise Exception('No search results')
    
    geom = results[0]['geometry']
    
    if not geom.has_key('bounds'):
        raise Exception('First result didn''t have bounds')
    
    sw = (geom['bounds']['southwest']['lat'], geom['bounds']['southwest']['lng'])
    ne = (geom['bounds']['northeast']['lat'], geom['bounds']['northeast']['lng'])
    
    conn.close()
    
    return sw, ne

def drange(start, stop, step):
    if step * start > step * stop:
        raise Exception('Invalid parameters %g, %g, %g', start, stop, step)
    
    if step == 0:
        raise Exception('Cannot have zero step')
    
    expect = (stop - start) / step
    
    d = start
    r = []
    while d < stop:
        r.append(d)
        d += step
    
    return r

'''
Make an equilateral-triangle grid across the bounding box defined by (sw, ne), spaced by at most
[resolution] number of meters.

  sw - the southwest (lat, lng) of the bounding box
  ne - the northeast --"--
  resolution - the maximal grid resolution, in meters

Returns
  A list of (lat, lng) tuples forming the grid. May be used directly queryLocations or 
    generateHeatmapHTML
'''
def makeGrid(sw, ne, resolution):
    # The Earth is ~40,075km in circumference
    c_earth = 40075000.0
    
    delta_lng = ne[1] - sw[1]
    if delta_lng < 0:
        raise Exception('Negative longitudinal extent.' +
            ' Does your city cross 180 degrees of longitude?')
            
    # A degree of longitude varies in metric length depending on the latitude.
    # We approximate by the value at the northern or southern extent, depending on which is further
    # from the equator.
    meters_to_lat = c_earth / 360.0
    
    if ne[0] > -sw[0]:
        meters_to_lng = meters_to_lat * math.cos(math.radians(ne[0]))
    else:
        meters_to_lng = meters_to_lat * math.cos(math.radians(sw[0]))
    
    # delta_lat is scaled down, since we're building a triangular grid
    delta_lat = math.sqrt(0.75) * resolution / meters_to_lat
    delta_lng = resolution / meters_to_lng
    
    lat_lng = []
    
    for i, lat in enumerate(drange(sw[0], ne[0], delta_lat)):
        if i % 2 is not 0:
            lng_offset = delta_lng / 2.0
        else:
            lng_offset = 0.0

        for lng in drange(sw[1], ne[1], delta_lng):
            lat_lng.append((lat, lng + lng_offset))
     
    return lat_lng

def generateHeatmapFiles(api_key, city_name, type_strs, **kwargs):
    if kwargs.has_key('lat_lngs'):
        lat_lngs = kwargs['lat_lngs']
    else:
        lat_lngs = queryCityBounds(city_name)

    if kwargs.has_key('template'):
        template = kwargs['template']
    else:
        template = 'heatmap.template'
    
    if kwargs.has_key('radius'):
        radius = kwargs['radius']
    else:
        radius = 6000
    
    if kwargs.has_key('method'):
        method = kwargs['method']
    else:
        method = 'nearby'
    
    if method == 'nearby':
        query_function = nearbyQueryPlaces        
    elif method == 'radar':
        query_function = radarQueryPlaces
    else:
        raise Exception('Method must be either ''nearby'' or ''radar'' ')

    for type_str in type_strs:
        results = query_function(api_key, type_str, lat_lngs, radius)
        generateHeatmapHTML(city_name, type_str, results, template)
        now = datetime.now()

        f_json = open('%s/%s.json' % (city_name, type_str), 'w')
        json.dump(results, f_json)
        f_json.close()
        
        f_json_archive = open('%s/%s_%d_%02d_%02d_%s.json' %
            (city_name, type_str, now.year, now.month, now.day, method), 'w')
        json.dump(results, f_json_archive)
        f_json_archive.close()


