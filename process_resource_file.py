from __future__ import absolute_import
from __future__ import print_function
import yaml

def process_resource_file(file_path):
    with open(file_path, encoding="utf-8") as resource:
        header = None
        content = None
        #Parse the file into the header and content sections
        for line in resource:
            if header is None:
                if not line.startswith('---\n'):
                    raise Exception('Cannot parse resource.')
                header = ''
            elif content is None:
                if line.startswith('---\n'):
                    content = ''
                else:
                    header += line
            else:
                content += line
        if content is None:
            print('Cannot parse resource: ', file_path)
            print('Missing second ---')
            print(header)
            return None
        resource_obj = yaml.load(header)
        resource_obj['content'] = content
        return resource_obj
