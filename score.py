#!/usr/bin/env python
from __future__ import absolute_import
from __future__ import print_function
import glob
import sqlite3
from process_resource_file import process_resource_file
from epitator.annotator import AnnoDoc, AnnoTier
from epitator.geoname_annotator import GeonameAnnotator, location_contains, GeonameRow
from epitator.get_database_connection import get_database_connection
from xml_tag_annotator import XMLTagAnnotator
import geoname_classifier
from expand_geonames import expand_geoname_id
from utils import combine_geotags


debug = False


def has_containment_relationship(a, b):
    if b == None:
        return False
    if a['geonameid'] == b['geonameid']:
        return True
    return location_contains(a, b) > 0 or location_contains(b, a) > 0


def score_LocationExtraction():

    gold_geotag_annotator = XMLTagAnnotator()
    geoname_annotator = GeonameAnnotator(geoname_classifier)

    gold_directory = './resolved_geoannotated_data/'
    gold_files = glob.glob(gold_directory + '*.md')

    tps = 0
    fps = 0
    fns = 0
    ignored = 0

    for gold_file in list(gold_files):
        processed = process_resource_file(gold_file)

        print(gold_file)

        doc = AnnoDoc(processed['content'])
        doc.add_tier(gold_geotag_annotator)
        doc.add_tier(geoname_annotator, show_features_for_geonameids=set(['7031697', '2950159', '5417618']))
        tags = doc.tiers['tags']
        connection = get_database_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        geoname_ids = set([span.label for span in tags
                       if span.tag_name != 'ignore'])
        geoname_ids |= set([span.geoname.geonameid for span in doc.tiers['geonames']])
        for geoname_id in list(geoname_ids):
            geoname_ids.update(expand_geoname_id(geoname_id))
        geoname_results = cursor.execute('''
        SELECT *
        FROM geonames
        WHERE geonameid IN
        (''' + ','.join('?' for x in geoname_ids) + ')', list(geoname_ids))
        geoname_results = [GeonameRow(r) for r in geoname_results]
        geonames_by_id = {r['geonameid']: r for r in geoname_results}
        extra_geonames = geoname_ids - set(geonames_by_id.keys())
        if extra_geonames != set():
            print("Warning! Extra annotated geonames were not found in sqlite3 database: ", extra_geonames)
        tags = combine_geotags(tags, geonames_by_id)

        spans_in_gold = tags.group_spans_by_containing_span(doc.tiers['geonames'], allow_partial_containment=True)
        for gold_span, gn_spans in spans_in_gold:
            if gold_span.tag_name == 'ignore':
                continue
            if any(expand_geoname_id(gold_span.label) & expand_geoname_id(gn_span.geoname['geonameid']) for gn_span in gn_spans):
                tps += 1
            else:
                if debug or gold_file.endswith('manual_annotations.md'):
                    print("FNeg:", gold_span, gold_span.text)
                    print([(span.metadata['geoname'].name, span.metadata['geoname'].geonameid,) for span in gn_spans])
                fns += 1
        gold_in_spans = doc.tiers['geonames'].group_spans_by_containing_span(
            tags, allow_partial_containment=True)
        for gn_span, gold_spans in gold_in_spans:
            if any(gold_span.tag_name == 'ignore' for gold_span in gold_spans):
                ignored += 1
                continue
            gold_span_ids = set()
            for gold_span in gold_spans:
                gold_span_ids.update(expand_geoname_id(gold_span.label))
            if not any(has_containment_relationship(geonames_by_id.get(geoname_id),
                                                    geonames_by_id.get(gold_span_id))
                       for geoname_id in expand_geoname_id(gn_span.geoname.geonameid)
                       for gold_span_id in gold_span_ids):
                if debug or gold_file.endswith('manual_annotations.md'):
                    print("FPos:", gn_span.text, gn_span.metadata['geoname'].geonameid, gn_span.metadata['geoname'].name)
                fps += 1
        print("\n")

    print('tps:', tps)
    print('fns:', fns)
    print('fps:', fps)
    print('ignored:', ignored)


if __name__ == '__main__':
    import datetime
    start = datetime.datetime.now()
    score_LocationExtraction()
    print("Finished in", datetime.datetime.now() - start)
