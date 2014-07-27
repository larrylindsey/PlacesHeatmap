import json
from httplib import HTTPSConnection

'''
Read a list of Google Places into a dict

  type_str - the type string used in the query. Can be single, like 'cafe', or multiple,
             as in 'cafe|bar'
  api_key - your api key
  lat_lngs - a list of lat,lng tuples. Each location will be queried and added to the
             dict

Returns
  a dict in which the keys are the unique id assigned to each place by Google, and the
    values are lat,lng tuples indicating the location of the given place.
    
  This function may throw HTTPSExceptions
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
        locs_dict = dict(locs_dict.items() + curr_locs.items())
    
    return locs_dict


