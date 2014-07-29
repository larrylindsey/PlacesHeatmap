PlacesHeatmap
=============

A set of dumb python scripts to generate heatmaps of interesting places (cafes, bars, etc) in cities.

Places Data
-----------

The data for place comes from the Google Places API, using a radar search (see the [API](https://developers.google.com/places/documentation/search))

One of the parameters you'll see in the code is the place type. This is not a generic term as it might be in a text search, but must be one of the ones that is [supported by the Places API](https://developers.google.com/places/documentation/supported_types)

Heatmaps
--------

The heatmap HTML code is a slight modification of what is found [here](https://developers.google.com/maps/documentation/javascript/examples/layer-heatmap)
