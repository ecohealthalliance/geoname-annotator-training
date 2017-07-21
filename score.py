#!/usr/bin/env python
import glob
import sys
from process_resource_file import process_resource_file
from epitator.annotator import AnnoDoc
from epitator.geoname_annotator import GeonameAnnotator, location_contains
from epitator.get_database_connection import get_database_connection
from xml_tag_annotator import XMLTagAnnotator
import geoname_classifier
import sqlite3

def safe_print(u):
    try:
        s = repr(u).encode('utf8', 'ignore')
    except UnicodeEncodeError as e:
        s = e
    print s

def score_LocationExtraction():

    gold_geotag_annotator = XMLTagAnnotator()
    geoname_annotator = GeonameAnnotator(geoname_classifier)

    gold_directory = './resolved_geoannotated_data/'
    gold_files = glob.glob(gold_directory + '*.md')

    all_gold_locations = []
    all_ga_locations = []

    tps = 0
    fps = 0
    tns = 0
    fns = 0
    ignored = 0

    i = 1
    for gold_file in gold_files:
        # Skip these because of many incorrect names
        if gold_file.endswith('/chL.txt.md'): continue
        if gold_file.endswith('/Barcelona-History.txt.md'): continue
        processed = process_resource_file(gold_file)

        print gold_file

        doc = AnnoDoc(unicode(processed['content'], 'utf8', 'ignore'))
        print "Annotating gold..."
        doc.add_tier(gold_geotag_annotator)
        print "Annotating geonames..."
        doc.add_tier(geoname_annotator)
        # Remove overlapping gold spans favoring the ignored ones and geospans
        tag_values = {
            'ignore': 100,
            'geo': 1
        }
        doc.tiers['tags'].filter_overlapping_spans(
            lambda span: tag_values.get(span.tag_name, 0))
        connection = get_database_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        geoname_ids = [span.label for span in doc.tiers['tags'].spans
                       if span.tag_name != 'ignore']
        geoname_results = cursor.execute('''
        SELECT *
        FROM geonames
        WHERE geonameid IN
        (''' + ','.join('?' for x in geoname_ids) + ')', geoname_ids)
        geonames_by_id = {r['geonameid']: r for r in geoname_results}
        assert(set(geoname_ids) - set(geonames_by_id.keys()) == set())
        def has_containment_relationship(a, b):
            if a['geonameid'] == b['geonameid']:
                return True
            return location_contains(a, b) > 0 or location_contains(b, a) > 0
        spans_in_gold = doc.tiers['tags'].group_spans_by_containing_span(doc.tiers['geonames'], allow_partial_containment=True)
        for gold_span, gn_spans in spans_in_gold:
            if gold_span.tag_name == 'ignore':
                continue
            if any(gold_span.label == gn_span.geoname['geonameid'] for gn_span in gn_spans):
                tps += 1
            else:
                fns += 1
        gold_in_spans = doc.tiers['geonames'].group_spans_by_containing_span(doc.tiers['tags'], allow_partial_containment=True)
        for gn_span, gold_spans in gold_in_spans:
            if any(gold_span.tag_name == 'ignore' for gold_span in gold_spans):
                ignored += 1
                continue
            if not any(has_containment_relationship(gn_span.geoname,
                                                    geonames_by_id[gold_span.label])
                       for gold_span in gold_spans):
                fps += 1
        print
        print
        print

    print 'tps:', tps
    print 'fns:', fns
    print 'fps:', fps
    print 'ignored:', ignored


if __name__ == '__main__':
    import datetime
    start = datetime.datetime.now()
    score_LocationExtraction()
    print "Finished in", datetime.datetime.now() - start
