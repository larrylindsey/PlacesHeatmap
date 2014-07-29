import json
import os
import string
import copy
from httplib import HTTPSConnection

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
    values are lat,lng tuples indicating the location of the given place.
    
  This function may raise HTTPSExceptions
'''
def queryLocations(api_key, type_str, lat_lngs, radius = 6000):
    url_template = '/maps/api/place/radarsearch/json?key=%s&location=%s&radius=%g&types=%s'
    
    conn = HTTPSConnection('maps.googleapis.com')
    
    locs_dict = dict()
    
    for lat_lng in lat_lngs:
        lat_lng_str = '%g,%g' % lat_lng
        url = url_template % (api_key, lat_lng_str, radius, type_str)
        conn.request('GET', url)
        req = conn.getresponse()
        
        if req.status != 200:
            raise Exception(req.reason)
        
        json_body = req.read()
        
        places_json = json.loads(json_body)
        curr_locs = {result['id'] :
            (result['geometry']['location']['lat'],
             result['geometry']['location']['lng'])
            for result in places_json['results']}
        print 'Found ' + str(len(curr_locs)) + ' places'
        locs_dict = dict(locs_dict.items() + curr_locs.items())
    
    print 'Returning ' + str(len(locs_dict)) + ' places'
    return locs_dict

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

def __generateViewDeclaration(var, latlngs):
    view_latlng = [0.0, 0.0]
    for latlng in latlngs:
        view_latlng[0] += latlng[0]
        view_latlng[1] += latlng[1]
    view_latlng[0] /= len(latlngs)
    view_latlng[1] /= len(latlngs)
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
def generateHeatmapHTML(api_key, city_name, type_strs, lat_lngs,
    template = 'heatmap.template', radius=6000):
    f_template = open(template, 'r')
    template_str = string.Template(f_template.read())
    f_template.close()
    
    if not os.path.exists(city_name):
        os.makedirs(city_name)
    
    for type_str in type_strs:
        html_name = city_name + '/' + type_str.replace('|', '_or_') + '.html'
        f_html = open(html_name, 'w')
        
        locs = queryLocations(api_key, type_str, lat_lngs, radius)
        places_declaration = __generatePlacesDeclaration('placeData', locs)
        view_declaration = __generateViewDeclaration('viewCenter', lat_lngs)
        
        html_str = copy.copy(template_str)
        
        f_html.write(html_str.substitute(place_data = places_declaration,
                                         view_data = view_declaration))
        f_html.close()
        

