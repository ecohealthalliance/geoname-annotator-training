"""
Train a geoname classifier using a set of articles annotated
with associated geonames ids.
The classifier is outputted as a self-contained python script.
"""
from __future__ import absolute_import
from __future__ import print_function
import glob
import sqlite3
import numpy as np
import re
import sklearn
import logging
import pprint
from process_resource_file import process_resource_file
from epitator.annotator import AnnoDoc, AnnoTier
from epitator.geoname_annotator import GeonameAnnotator, GeonameFeatures, GeonameRow
from epitator.get_database_connection import get_database_connection
from xml_tag_annotator import XMLTagAnnotator
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_validate
from expand_geonames import expand_geoname_id
from utils import combine_geotags

logging.getLogger('annotator.geoname_annotator').setLevel(logging.ERROR)

city_state_code_re = re.compile(r"^(PPL|ADM|PCL)")

geoname_annotator = GeonameAnnotator()

HIGH_CONFIDENCE_THRESHOLD = 0.5
GEONAME_SCORE_THRESHOLD = 0.13

EXPAND_GEONAMES = False

def train_classifier(annotated_articles, prior_classifier=None):
    """
    Train a classifier using the given set of annotated articles.
    """
    labels = []
    weights = []
    feature_vectors = []
    for article in annotated_articles:
        gold_locations = set()
        for geonameid in article.get('geonameids'):
            assert isinstance(geonameid, str)
            if EXPAND_GEONAMES:
                expanded_geonames = expand_geoname_id(geonameid)
                gold_locations.update(expanded_geonames)
            else:
                gold_locations.add(geonameid)
        doc = AnnoDoc(article['content'])
        candidates = geoname_annotator.get_candidate_geonames(doc)
        gn_features = geoname_annotator.extract_features(candidates, doc)
        if prior_classifier:
            geoname_annotator.add_contextual_features(
                candidates, gn_features,
                prior_classifier.predict_proba, HIGH_CONFIDENCE_THRESHOLD)
        used_gold_locations = set()
        for geoname, feature in zip(candidates, gn_features):
            if all([
                len(span_group) > 0
                for span, span_group in AnnoTier(geoname.spans)\
                    .group_spans_by_containing_span(article['sections_to_ignore'],
                                                    allow_partial_containment=True)]):
                # print("ignoring:", geoname['name'])
                continue
            feature_vectors.append(feature.values())
            weights.append(len(geoname.spans) * (2 if city_state_code_re.match(geoname.feature_code) else 1))
            geonameid = geoname['geonameid']
            if EXPAND_GEONAMES:
                if expand_geoname_id(geonameid) & gold_locations:
                    used_gold_locations |= expand_geoname_id(geonameid)
                    labels.append(True)
                else:
                    labels.append(False)
            else:
                labels.append(geonameid in gold_locations)
                used_gold_locations.add(geonameid)
        print("unused gold locations:", gold_locations - used_gold_locations)
    # L1 regularization helps with overfitting by constraining the model
    # to use fewer variables.
    clf = LogisticRegression(
        penalty='l1',
        C=0.1,
        solver='liblinear')
    cv_results = cross_validate(clf, feature_vectors, labels, fit_params=dict(sample_weight=weights), cv=5, scoring=('f1',), return_estimator=True)
    max_score = 0
    print("Cross validation f-scores:")
    for idx, score in enumerate(cv_results['test_f1']):
        print(score)
        if score > max_score:
            max_score = score
            clf = cv_results['estimator'][idx]
    print("Number of examples: " + str(len(feature_vectors)))
    print("Number of positive labels: " + str(np.array(labels).sum()))
    clf.feature_names = GeonameFeatures.feature_names
    return clf

# Load the annotated articles
gold_directory = './resolved_geoannotated_data/'
gold_files = glob.glob(gold_directory + '*.md')
annotated_articles = []
gold_geotag_annotator = XMLTagAnnotator()
for gold_file in gold_files:
    p = process_resource_file(gold_file)
    p['__path__'] = gold_file
    doc = AnnoDoc(p['content'])
    doc.add_tier(gold_geotag_annotator)
    tags = doc.tiers['tags']
    connection = get_database_connection()
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    geoname_ids = set([span.label for span in tags
                   if span.tag_name != 'ignore'])
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
    p['content'] = doc.text
    p['sections_to_ignore'] = AnnoTier([
        span for span in tags
        if span.tag_name == 'ignore'])
    if 'geonameids' not in p:
        p['geonameids'] = set(span.attrs['id'] for span in tags if span.tag_name != 'ignore')
    annotated_articles.append(p)


# First a high base classifier is trained to identify high confidence geonames.
# Next, a classifier that uses contextual features from the high confidence geonames
# is trained to identify geonames with greater accuracy.
base_classifier = train_classifier(annotated_articles)
contextual_classifier = train_classifier(annotated_articles, base_classifier)

# Print out a python program with a stand-alone version of the trained classifier.
# The problem with pickling it is that it will create a dependency on specific
# scikit-learn versions.


def pprint_clf(clf):
    """
    Helper function for printing classifier data with comments labeling the
    feature values.
    """
    result = "{\n"
    for k, v in clf.__dict__.items():
        if k == "coef_":
            result += "    '" + k + "': array([[\n"
            for feature, feature_name in zip(v[0], clf.feature_names):
                result += "        # " + feature_name + "\n"
                result += "        " + str(feature) + ",\n"
            result += "    ]]),\n"
        elif k == "feature_names":
            continue
        else:
            result += "    '" + k + "': " + pprint.pformat(v) + ",\n"
    result += "}\n"
    return result

with open('geoname_classifier.py', 'w') as f:
    f.write('''"""
This script was generated by the train.py script in this repository:
https://github.com/ecohealthalliance/geoname-annotator-training
"""
import numpy as np
from numpy import array, int32

''')
    f.write('''
HIGH_CONFIDENCE_THRESHOLD = ''' + str(HIGH_CONFIDENCE_THRESHOLD))
    f.write('''
GEONAME_SCORE_THRESHOLD = ''' + str(GEONAME_SCORE_THRESHOLD))
    f.write('''
base_classifier =\\\n''' + pprint_clf(base_classifier))
    f.write('''
contextual_classifier =\\\n''' + pprint_clf(contextual_classifier))
    f.write('''
# Logistic regression code from scipy
def predict_proba(X, classifier):
    """Probability estimation for OvR logistic regression.
    Positive class probabilities are computed as
    1. / (1. + np.exp(-classifier.decision_function(X)));
    multiclass is handled by normalizing that over all classes.
    """
    prob = np.dot(X, classifier['coef_'].T) + classifier['intercept_']
    prob = prob.ravel() if prob.shape[1] == 1 else prob
    prob *= -1
    np.exp(prob, prob)
    prob += 1
    np.reciprocal(prob, prob)
    if prob.ndim == 1:
        return np.vstack([1 - prob, prob]).T
    else:
        # OvR normalization, like LibLinear's predict_probability
        prob /= prob.sum(axis=1).reshape((prob.shape[0], -1))
        return prob


def predict_proba_base(X):
    return predict_proba(X, base_classifier)


def predict_proba_contextual(X):
    return predict_proba(X, contextual_classifier)
''')
