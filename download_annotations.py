import requests
import yaml
import os

def create_resource_file(location, data):
    directory = os.path.dirname(location)
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(location, 'w+') as file:
        file.write('---\n')
        yaml_string = yaml.safe_dump({ k:v for k, v in data.items() if k != '_content'})
        file.write(yaml_string)
        file.write('---\n')
        if '_content' in data:
            file.write(data['_content'].encode('utf8'))

def annotations_to_annie_training_docs():
    resp = requests.get("http://localhost:3000/api/geoannotatedDocuments",
      params={
        "limit": 10000
      })
    for item in resp.json():
        del item['content']
        del item['enhancements']
        item['_content'] = item['annotatedContent']
        del item['annotatedContent']
        create_resource_file(
            './resolved_geoannotated_data/' + '_'.join(item['_sourceId'].split('/')) + '.md',
            item)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    annotations_to_annie_training_docs()