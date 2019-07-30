#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import requests
import yaml
import os

def create_resource_file(location, data):
    directory = os.path.dirname(location)
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(location, 'w+', encoding='utf8') as file:
        file.write('---\n')
        yaml_string = yaml.safe_dump({ k:v for k, v in data.items() if k != '_content'})
        file.write(yaml_string)
        file.write('---\n')
        if '_content' in data:
            file.write(data['_content'])

def annotations_to_annie_training_docs():
    resp = requests.get(os.environ.get(
        "GEONAME_CURATOR_URL",
        "https://geoname-curator.eha.io") + "/api/geoannotatedDocuments",
      params={
        "limit": 10000
      })
    resp.raise_for_status()
    for item in resp.json():
        del item['content']
        del item['enhancements']
        item['_content'] = item['annotatedContent']
        del item['annotatedContent']
        print(item['_sourceId'])
        create_resource_file(
            './resolved_geoannotated_data/' + '_'.join(item['_sourceId'].split('/')) + '.md',
            item)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    annotations_to_annie_training_docs()
