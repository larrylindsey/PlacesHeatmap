import json
import os
import string
import copy
import math
import time
from datetime import datetime
from httplib import HTTPSConnection
from httplib import HTTPConnection


def drange(start, stop, step):
    if step * start > step * stop:
        raise Exception('Invalid parameters %g, %g, %g', start, stop, step)

    if step == 0:
        raise Exception('Cannot have zero step')

    d = start
    r = []
    while d < stop:
        r.append(d)
        d += step

    return r


class MeshPoint:
    def __init__(self, lat_lng, r, triangles=None):
        self.__lat_lng = lat_lng
        self.__r = r
        if triangles is None:
            self.__triangles = []
        else:
            self.__triangles = triangles

    def __eq__(self, other):
        return self.lat_lng()[0] == other.lat_lng()[0] and self.lat_lng()[1] == other.lat_lng()[1]\
            and self.r() == other.r()

    def __hash__(self):
        return 37 * hash(self.__lat_lng[0]) + hash(self.__lat_lng[1])

    def __str__(self):
        return '(' + str(self.__r) + ') ' + str(self.__lat_lng[0]) + ', ' + str(self.__lat_lng[1])

    def r(self):
        return self.__r

    def lat_lng(self):
        return self.__lat_lng

    def add_triangles(self, triangles):
        self.__triangles.extend(triangles)

    def add_triangle(self, triangle):
        self.__triangles.append(triangle)

    def triangles(self):
        return list(self.__triangles)

    def refine(self):
        triangles = list(self.__triangles)
        for triangle in triangles:
            triangle.split()
        self.__r /= 2

    def replace_triangle(self, old_tri, new_tri):
        self.__triangles.remove(old_tri)
        self.__triangles.append(new_tri)


class MeshTriangle:
    def __init__(self, mp_triplet, r, pt_tri_map=None):
        self.__triplet = mp_triplet
        self.__nbd = []
        self.__r = r

        if pt_tri_map is None:
            self.__map = dict()
        else:
            self.__map = pt_tri_map

    def __str__(self):
        sep = ''
        str_rep = '[' + str(self.__r) + '] '
        for tri in self.__triplet:
            str_rep += sep + str(tri)
            sep = ' -> '
        return str_rep

    def __mid(self, mp_a, mp_b):
        a = mp_a.lat_lng()
        b = mp_b.lat_lng()

        tri_list = []
        mp_ab = MeshPoint(((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0), self.__r / 2.0, tri_list)

        if mp_ab in self.__map:
            keys = self.__map.keys()
            idx = keys.index(mp_ab)
            return keys[idx]
        else:
            self.__map[mp_ab] = tri_list
            return mp_ab

    def __eq__(self, other):
        return self.points() == other.points() and self.r() == other.r()

    def __hash__(self):
        hval = hash(self.r())
        for point in self.points():
            hval *= 37
            hval += hash(point)
        return hval

    def r(self):
        return self.__r

#    def add_neighbor(self, mesh_point):
#        self.__nbd.append(mesh_point)
#
#    def get_neighbors(self):
#        return list(self.__nbd)

    def points(self):
        return list(self.__triplet)

    def split(self):
        half_r = self.__r / 2.0
        # The triplet is like ABC. First, calculate midpoints AB, BC, and CA
        (pt_a, pt_b, pt_c) = self.__triplet
        pt_ab = self.__mid(pt_a, pt_b)
        pt_bc = self.__mid(pt_b, pt_c)
        pt_ca = self.__mid(pt_c, pt_a)

        a_ab_ca = MeshTriangle([pt_a, pt_ab, pt_ca], half_r, self.__map)
        ab_b_bc = MeshTriangle([pt_ab, pt_b, pt_bc], half_r, self.__map)
        ca_bc_c = MeshTriangle([pt_ca, pt_bc, pt_c], half_r, self.__map)
        ab_bc_ca = MeshTriangle([pt_ab, pt_bc, pt_ca], half_r, self.__map)

        pt_a.replace_triangle(self, a_ab_ca)
        pt_b.replace_triangle(self, ab_b_bc)
        pt_c.replace_triangle(self, ca_bc_c)
        pt_ab.add_triangles([a_ab_ca, ab_b_bc, ab_bc_ca])
        pt_bc.add_triangles([ab_b_bc, ca_bc_c, ab_bc_ca])
        pt_ca.add_triangles([a_ab_ca, ca_bc_c, ab_bc_ca])

        return [a_ab_ca, ab_b_bc, ca_bc_c, ab_bc_ca]


class Mesh:
    def __init__(self, **kwargs):
        #self.__mesh = []
        self.__pt_tri_map = dict()

        if 'sw' in kwargs and 'ne' in kwargs and 'r' in kwargs:
            self.__initialize_mesh(kwargs['sw'], kwargs['ne'], kwargs['r'])
        elif 'triangles' in kwargs:
            self.__recreate_mesh(kwargs['triangles'])
        else:
            raise Exception('A Mesh must be instantiated with either sw/ne bounds and a radius or a triangle dict')

    def __eq__(self, other):
        ok = True
        our_pts = self.get_points()
        their_pts = other.get_points()

        for pt in our_pts:
            if pt not in their_pts:
                print pt, 'was not in other'
                ok = False

        our_tris = self.__get_triangles()
        their_tris = other.__get_triangles()
        for tri in our_tris:
            if tri not in their_tris:
                print str(tri), 'was not in other'
                ok = False

        return ok

    def __get_triangles(self):
        tri_set = set()
        for point in self.get_points():
            for triangle in self.__pt_tri_map[point]:
                tri_set.add(triangle)
        return tri_set

    def get_points(self):
        return list(self.__pt_tri_map.keys())

    def to_dict(self):
        mesh_dict = dict()
        point_list = []
        tri_list = []

        idx_point_map = dict()
        tri_set = set()

        # first pass:
        #  a) build a map point -> i
        #  b) insert point dict into point_list like
        #      'i':       index
        #      'lat_lng': location
        #      'r':       search radius
        # c) Populate the triangle set
        for i, point in enumerate(self.__pt_tri_map.keys()):
            point_list.append({'idx': i, 'lat_lng': point.lat_lng(), 'r': point.r()})
            idx_point_map[point] = i
            for triangle in self.__pt_tri_map[point]:
                tri_set.add(triangle)

        # second pass:
        #   insert triangle dict into tri_list like
        #     'tri_idx': a list of the indices (as in point_list) of the points belonging to this triangle
        #     'r':       the search radius for this triangle (redundant?)
        for triangle in tri_set:
            tri_list.append({'tri_idx': [idx_point_map[point] for point in triangle.points()],
                             'r': triangle.r()})

        mesh_dict['points'] = point_list
        mesh_dict['triangles'] = tri_list

        return mesh_dict

    def __recreate_mesh(self, triangles):
        if 'points' not in triangles or 'triangles' not in triangles:
            raise Exception('triangle dict must have keys ''points'' and ''triangles''')

        idx_point_map = dict()

        for point_dict in triangles['points']:
            idx = int(point_dict['idx'])
            lat_lng = map(float, point_dict['lat_lng'])
            r = float(point_dict['r'])
            pt_tri_list = []
            point = MeshPoint(lat_lng, r, pt_tri_list)
            idx_point_map[idx] = point
            self.__pt_tri_map[point] = pt_tri_list

        for tri_dict in triangles['triangles']:
            tri_pt = [idx_point_map[idx] for idx in map(int, tri_dict['tri_idx'])]
            r = float(tri_dict['r'])
            triangle = MeshTriangle(tri_pt, r, self.__pt_tri_map)
            for point in tri_pt:
                point.add_triangle(triangle)

    def __initialize_mesh(self, sw, ne, r):
        grid, pt_tri_map = self.__make_grid(sw, ne, r)
        #triangles = self.__triangles

        for i in range(0, len(grid) - 2, 2):
            # b:  * * * (*)
            # a: * * * *
            pt_a = grid[i]
            pt_b = grid[i + 1]

            for j in range(0, len(pt_a) - 1):
                # of the form  *
                #             * *
                triangle = MeshTriangle((pt_a[j], pt_a[j + 1], pt_b[j]), r, pt_tri_map)

                #triangles.append(triangle)
                pt_a[j].add_triangle(triangle)
                pt_a[j + 1].add_triangle(triangle)
                pt_b[j].add_triangle(triangle)

                # of the form * *
                #              *
                if j + 1 < len(pt_b):
                    triangle = MeshTriangle((pt_a[j + 1], pt_b[j], pt_b[j + 1]), r, pt_tri_map)

                    #triangles.append(triangle)
                    pt_a[j + 1].add_triangle(triangle)
                    pt_b[j].add_triangle(triangle)
                    pt_b[j + 1].add_triangle(triangle)

        for i in range(1, len(grid) - 1, 2):
            # b: * * * *
            # a:  * * * (*)
            pt_a = grid[i]
            pt_b = grid[i + 1]

            for j in range(0, len(pt_b) - 1):
                # of the form * *
                #              *
                triangle = MeshTriangle((pt_a[j], pt_b[j], pt_b[j + 1]), r, pt_tri_map)

                #triangles.append(triangle)
                pt_a[j].add_triangle(triangle)
                pt_b[j].add_triangle(triangle)
                pt_b[j + 1].add_triangle(triangle)

                # of the form  *
                #             * *
                if j + 1 < len(pt_a):
                    triangle = MeshTriangle((pt_a[j], pt_a[j + 1], pt_b[j + 1]), r, pt_tri_map)

                    #triangles.append(triangle)
                    pt_a[j].add_triangle(triangle)
                    pt_a[j + 1].add_triangle(triangle)
                    pt_b[j + 1].add_triangle(triangle)

        self.__pt_tri_map = pt_tri_map


    '''
    Creates a list of lists. Each inner list contains a single raster across longitude for a different latitude.
    Each lat_lng sample is at most r meters from its nearest neighbors. The sampling pattern approximates a mesh of
    equilateral triangles, like

      * * *
     * * * *
      * * *
     * * * *

      sw - the southwest corner bounding the sample mesh region
      ne - the northeast corner --"--
      r - the minimum distance between nearest neighbors

    This function is kind of dumb. If the bounded region overlaps 180 degrees of longitude, it will raise an Exception.
    It makes a flat approximation of lat/lng across the globe, meaning that near the equator things will be as accurate
    as possible, but samples will be closer together at the extreme latitudes, especially for large regions near the
    poles.
    '''
    @staticmethod
    def __make_grid(sw, ne, r):
        # The Earth is ~40,075km in circumference
        c_earth = 40075000.0
        point_triangle_map = dict()

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
        delta_lat = math.sqrt(0.75) * r / meters_to_lat
        delta_lng = r / meters_to_lng

        points_ll = []

        for i, lat in enumerate(drange(sw[0], ne[0], delta_lat)):
            points = []
            points_ll.append(points)
            if i % 2 is not 0:
                lng_offset = delta_lng / 2.0
            else:
                lng_offset = 0.0

            for lng in drange(sw[1], ne[1], delta_lng):
                lat_lng = (lat, lng + lng_offset)
                triangles = []
                point = MeshPoint(lat_lng, r, triangles)
                point_triangle_map[point] = triangles
                points.append(point)

        return points_ll, point_triangle_map

    def get_points(self):
        return list(self.__pt_tri_map.keys())

    def refine(self, triangle):
        if triangle in self.__mesh:
            new_triangles = triangle.split()
            self.__mesh.remove(triangle)
            self.__mesh.extend(new_triangles)
            return new_triangles
        else:
            raise Exception('Attempted to refine a triangle that is not in the mesh')


class PlacesQuery:
    def __init__(self, key, **kwargs):
        self.__api_key = key
        self.__param_dict = dict()
        self.__radius = 3000
        self.__city = ''
        self.__locs_dict = dict()
        self.__locs = dict()
        self.__lat_lngs = []
        self.__query = self.__radar_query
        self.__param_string = None
        self.__sw = None
        self.__ne = None

        if 'radius' in kwargs:
            self.__radius = kwargs['radius']

        if 'city' in kwargs:
            self.__city = kwargs['city']

        # see https://developers.google.com/places/documentation/search
        for key in ('keyword', 'language', 'minprice', 'maxprice', 'name', 'opennow', 'rankby', 'types'):
            if key in kwargs:
                self.__param_dict[key] = kwargs[key]

        if 'method' in kwargs:
            self.set_method(kwargs['method'])

    @staticmethod
    def __read_url(conn, url):
        conn.request('GET', url)
        req = conn.getresponse()

        if req.status != 200:
            raise Exception(req.reason)

        json_body = req.read()
        places_json = json.loads(json_body)
        return places_json

    @staticmethod
    def __results_to_locations(result_dict):
        return {result['id']: (result['geometry']['location']['lat'],
                               result['geometry']['location']['lng'])
                for result in result_dict.values()}

    '''
    A helper function to generate a javascript variable declaration for text replacement.

      var - the variable name to declare
      locs - a dict in which the values are lat,lng tuples

    Returns
      a string that when run in javascript, will declare the requested variable.

    '''
    @staticmethod
    def __generate_places_declaration(var_name, locs):
        declaration = var_name + ' = [\n'
        for latlng in locs.values():
            declaration += '  new google.maps.LatLng(%g, %g),\n' % latlng
        declaration += '];'
        return declaration

    @staticmethod
    def __generate_view_declaration(var_name, locs):
        view_latlng = [0.0, 0.0]
        for latlng in locs.values():
            view_latlng[0] += latlng[0]
            view_latlng[1] += latlng[1]
        view_latlng[0] /= len(locs)
        view_latlng[1] /= len(locs)
        view_latlng = tuple(view_latlng)
        declaration = var_name + ' = new google.maps.LatLng(%g, %g);' % view_latlng
        return declaration

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
    def __radar_query(self):
        url_template = '/maps/api/place/radarsearch/json?key=%s&location=%s&radius=%g'

        conn = HTTPSConnection('maps.googleapis.com')

        locs_dict = dict()

        for lat_lng in self.__lat_lngs:
            lat_lng_str = '%g,%g' % lat_lng
            url = url_template % (self.__api_key, lat_lng_str, self.__radius)
            for key in self.__param_dict:
                url += '&' + key + '=' + self.__param_dict[key]

            places_json = self.__read_url(conn, url)

            curr_locs = {result['id']: result for result in places_json['results']}
            print 'Found ' + str(len(curr_locs)) + ' places'
            locs_dict = dict(locs_dict.items() + curr_locs.items())

        conn.close()
        print 'Returning ' + str(len(locs_dict)) + ' places'

        return locs_dict

    def __nearby_query(self):
        url_template = '/maps/api/place/nearbysearch/json?key=%s&location=%s&radius=%g'
        next_url_template = '/maps/api/place/nearbysearch/json?key=%s&pagetoken=%s'
        conn = HTTPSConnection('maps.googleapis.com')

        locs_dict = dict()

        for lat_lng in self.__lat_lngs:
            lat_lng_str = '%g,%g' % lat_lng
            url = url_template % (self.__api_key, lat_lng_str, self.__radius)

            for key in self.__param_dict:
                url = url + '&' + key + '=' + self.__param_dict[key]

            places_json = self.__read_url(conn, url)

            curr_locs = {result['id']: result for result in places_json['results']}
            locs_dict = dict(locs_dict.items() + curr_locs.items())
            count = len(curr_locs)

            while 'next_page_token' in places_json:
                next_token = places_json['next_page_token']
                url = next_url_template % (self.__api_key, next_token)

                time.sleep(0.5)
                places_json = self.__read_url(conn, url)

                while places_json['status'] == 'INVALID_REQUEST':
                    time.sleep(0.5)
                    places_json = self.__read_url(conn, url)

                curr_locs = {result['id']: result for result in places_json['results']}
                locs_dict = dict(locs_dict.items() + curr_locs.items())

                count += len(curr_locs)

            print 'Found ' + str(count) + ' places'

        conn.close()

        print 'Returning ' + str(len(locs_dict)) + ' places'
        return locs_dict

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
    def __search_city_bounds(self):
        url = '/maps/api/geocode/json?address=' + self.__city + '&sensor=false'
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

        if not 'bounds' in geom:
            raise Exception('First result didn''t have bounds')

        sw = (geom['bounds']['southwest']['lat'], geom['bounds']['southwest']['lng'])
        ne = (geom['bounds']['northeast']['lat'], geom['bounds']['northeast']['lng'])

        conn.close()

        self.__sw = sw
        self.__ne = ne

    def set_bounds(self, sw, ne):
        self.__sw = sw
        self.__ne = ne

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
    def make_grid(self):
        # The Earth is ~40,075km in circumference
        c_earth = 40075000.0

        if self.__sw is None or self.__ne is None:
            self.__search_city_bounds()

        sw = self.__sw
        ne = self.__ne

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
        delta_lat = math.sqrt(0.75) * self.__radius / meters_to_lat
        delta_lng = self.__radius / meters_to_lng

        lat_lng = []

        for i, lat in enumerate(drange(sw[0], ne[0], delta_lat)):
            if i % 2 is not 0:
                lng_offset = delta_lng / 2.0
            else:
                lng_offset = 0.0

            for lng in drange(sw[1], ne[1], delta_lng):
                lat_lng.append((lat, lng + lng_offset))

        self.__lat_lngs = lat_lng

    def param_string(self):
        if self.__param_string is None:
            pstr = ''
            sep = ''

            if 'types' in self.__param_dict:
                pstr += sep + self.__param_dict['types'].replace('|', '_or_')
                sep = '_'

            if 'keyword' in self.__param_dict:
                pstr += sep + self.__param_dict['keyword']

            self.__param_string = pstr

        return self.__param_string

    def set_param_string(self, pstr):
        self.__param_string = pstr

    def set_method(self, method):
        if method == 'radar':
            self.__query = self.__radar_query
        elif method == 'nearby':
            self.__query = self.__nearby_query
        else:
            raise Exception('Invalid method: ' + method + ', must be either radar or nearby')

    def set_radius(self, radius):
        self.__radius = radius

    def set_city(self, city):
        self.__city = city

    def get_radius(self):
        return self.__radius

    def get_city(self):
        return self.__city

    def get_grid(self):
        return self.__lat_lngs

    def query(self):
        if len(self.__param_dict) == 0:
            raise Exception('No type or keyword terms')
        self.__locs_dict = self.__query()
        self.__locs = self.__results_to_locations(self.__locs_dict)

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
    def to_html(self, template='heatmap.template'):

        f_template = open(template, 'r')
        template_str = string.Template(f_template.read())
        f_template.close()

        if not os.path.exists(self.__city):
            os.makedirs(self.__city)

        html_name = self.__city + '/' + self.param_string() + '.html'
        f_html = open(html_name, 'w')

        if len(self.__locs) == 0:
            self.query()

        places_declaration = self.__generate_places_declaration('placeData', self.__locs)
        view_declaration = self.__generate_view_declaration('viewCenter', self.__locs)

        html_str = copy.copy(template_str)

        f_html.write(html_str.substitute(place_data=places_declaration,
                                         view_data=view_declaration))
        f_html.close()

    def to_json(self):
        now = datetime.now()

        if len(self.__locs_dict) == 0:
            self.query()

        f_json = open('%s/%s.json' % (self.__city, self.param_string()), 'w')
        json.dump(self.__locs_dict, f_json)
        f_json.close()

        f_json_archive = open('%s/%s_%d_%02d_%02d.json' %
                              (self.__city, self.param_string(), now.year, now.month, now.day), 'w')
        json.dump(self.__locs_dict, f_json_archive)
        f_json_archive.close()
