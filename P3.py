#!/usr/bin/env python
import xml.etree.cElementTree as ET
from pprint import pprint
import re
import codecs
import json
import string

from collections import defaultdict
street_types = defaultdict(set)

lower = re.compile(r'^([a-z]|_)*$')
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

CREATED = [ "version", "changeset", "timestamp", "user", "uid"]

street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)
expected = ["Street", "Avenue", "Boulevard", "Drive", "Court", "Place", "Square", "Lane", "Road", 
            "Trail", "Parkway", "Commons", "Terrace", "Way", "Walk", "Pike", "Park", "Circle",
            "Broadway", "Alley", "Dale", "Champions", "Esplanade", "Green", "Limestone"]

mapping = {
    "St": "Street",
    "Ave": "Avenue",
    "Blvd": "Boulevard",
    "Dr": "Drive",
    "DR": "Drive",
    "Ct": "Court",
    "Courth": "Court", # spelling error
    "Pl": "Place",
    "Sq": "Square",
    "Ln": "Lane",
    "Rd.": "Road",
    "Rd": "Road",
    "Trl": "Trail",
    "Pkwy": "Parkway",
    "Ter": "Terrace",
}

cardinals = {
    "N": "North",
    "E": "East",
    "S": "South",
    "W": "West",
}

def update_name(street_name):
    # don't update yet
    #return street_name

    name = string.capwords(street_name)
    name = re.sub(r'Ne$', 'NE', name) # Keep NE instead of replace w/ Northeast
    name = name.strip(' .') # Remove trailing period

    if name.startswith('524 '):
        name = name.replace('524 ', '')

    for abbr, full in mapping.iteritems():
        # Check for abbreviations at the end of the street name
        if ' %s' % abbr in name:
            name = re.sub(r'{}$'.format(abbr), full, name)

    for abbr, full in cardinals.iteritems():
        # Check for abbreviations at the beginning of the street name
        if '%s. ' % abbr in name:
            name = re.sub(r'^{}.'.format(abbr), full, name)
        elif '%s ' % abbr in name:
            name = re.sub(r'^{}'.format(abbr), full, name)

    return name

def audit_street_type(street_name):
    m = street_type_re.search(street_name)
    if m:
        street_type = m.group()
        if street_type not in expected:
            street_types[street_type].add(street_name)

        
def shape_element(el):
    node = {}
    if el.tag == "node" or el.tag == "way":
        """
        {
"id": "2406124091",
"type: "node",
"visible":"true",
"created": {
          "version":"2",
          "changeset":"17206049",
          "timestamp":"2013-08-03T16:43:42Z",
          "user":"linuxUser16",
          "uid":"1219059"
        },
"pos": [41.9757030, -87.6921867],
"address": {
          "housenumber": "5157",
          "postcode": "60625",
          "street": "North Lincoln Ave"
        },
"amenity": "restaurant",
"cuisine": "mexican",
"name": "La Cabana De Don Luis",
"phone": "1 (773)-271-5176"
}
 <node id="261114295" visible="true" version="7" changeset="11129782" timestamp="2012-03-28T18:31:23Z" user="bbmiller" uid="451048" lat="41.9730791" lon="-87.6866303"/>
        """
        node['id'] = el.attrib['id']
        node['type'] = el.tag
        try:
            node['visible'] = el.attrib['visible']
        except KeyError:
            pass
        node['created'] = {}
        node['created']['version'] = el.attrib['version']
        node['created']['changeset'] = el.attrib['changeset']
        node['created']['timestamp'] = el.attrib['timestamp']
        node['created']['user'] = el.attrib['user']
        node['created']['uid'] = el.attrib['uid']
        try:
            node['pos'] = []
            node['pos'].append(float(el.attrib['lat']))
            node['pos'].append(float(el.attrib['lon']))
        except KeyError:
            del node['pos']
        node['address'] = {}
        node['node_refs'] = []
                
        for child in el:
            if 'k' in child.attrib and child.attrib['k'] == 'addr:street':
                #audit_street_type(child.attrib['v'])
                node['address']['street'] = update_name(child.attrib['v'])

                if child.attrib['v'].startswith('524 '):
                    node['address']['housenumber'] = '524'
            elif 'k' in child.attrib and child.attrib['k'] == 'addr:city':
                node['address']['city'] = child.attrib['v']
            elif 'k' in child.attrib and child.attrib['k'] == 'addr:state':
                node['address']['state'] = child.attrib['v']
            elif 'k' in child.attrib and child.attrib['k'] == 'addr:postcode':
                node['address']['postcode'] = child.attrib['v']
            elif 'k' in child.attrib and child.attrib['k'] == 'addr:housenumber':
                node['address']['housenumber'] = child.attrib['v']
            elif 'k' in child.attrib and child.attrib['k'] in ['addr:name', 'name']:
                node['name'] = child.attrib['v']
            elif 'k' in child.attrib and child.attrib['k'] in ['addr:phone', 'phone']:
                node['phone'] = child.attrib['v']
            elif 'k' in child.attrib and child.attrib['k'] == 'gnis:county_name':
                node['address']['county'] = child.attrib['v']
            elif 'k' in child.attrib and child.attrib['k'] in ['addr:amenity', 'amenity']:
                node['amenity'] = child.attrib['v']
            elif 'k' in child.attrib and child.attrib['k'] in ['addr:cuisine', 'cuisine']:
                node['cuisine'] = child.attrib['v']
            elif 'k' in child.attrib and child.attrib['k'] == 'bicycle':
                node['bicycle'] = child.attrib['v']
            elif 'ref' in child.attrib and child.tag == 'nd':
                node['node_refs'].append(child.attrib['ref'])
            
        if node['address'] == {}:
            del node['address']
        if node['node_refs'] == []:
            del node['node_refs']
        
        return node
    else:
        return None


def process_map(file_in, pretty = False):
    # You do not need to change this file
    file_out = "{0}.json".format(file_in)
    #data = []
    with codecs.open(file_out, "w") as fo:
        for _, element in ET.iterparse(file_in):
            el = shape_element(element)
            if el:
                #data.append(el)
                if pretty:
                    fo.write(json.dumps(el, indent=2)+"\n")
                else:
                    fo.write(json.dumps(el) + "\n")
    #return data

def test():
    process_map('lexington_kentucky.osm', False)
    #pprint(dict(street_types))
    

if __name__ == "__main__":
    test()
