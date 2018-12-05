"""
Train a geoname classifier using a set of articles annotated
with associated geonames ids.
The classifier is outputted as a self-contained python script.
"""
from __future__ import absolute_import
from __future__ import print_function
import glob
import sys
from process_resource_file import process_resource_file
from epitator.annotator import AnnoDoc, AnnoTier
from epitator.geoname_annotator import GeonameAnnotator, GeonameFeatures
from xml_tag_annotator import XMLTagAnnotator
from sklearn.linear_model import LogisticRegression
import numpy as np
import sklearn
import logging
import json
import pprint

logging.getLogger('annotator.geoname_annotator').setLevel(logging.ERROR)

geoname_annotator = GeonameAnnotator()

HIGH_CONFIDENCE_THRESHOLD = 0.5
GEONAME_SCORE_THRESHOLD = 0.1

def train_classifier(annotated_articles, prior_classifier=None):
    """
    Train a classifier using the given set of annotated articles.
    """
    labels = []
    feature_vectors = []
    for article in annotated_articles:
        gold_locations = set(map(str, article.get('geonameids')))
        doc = AnnoDoc(article['content'])
        candidates = geoname_annotator.get_candidate_geonames(doc)
        gn_features = geoname_annotator.extract_features(candidates, doc)
        if prior_classifier:
            scores = prior_classifier.predict_proba([f.values() for f in gn_features])
            for location, feature, score in zip(candidates, gn_features, scores):
                location.high_confidence = float(score[1]) > HIGH_CONFIDENCE_THRESHOLD
                feature.set_value('high_confidence', location.high_confidence)
            geoname_annotator.add_contextual_features(gn_features)
        used_gold_locations = set()
        for geoname, feature in zip(candidates, gn_features):
            if all([
                len(span_group) > 0
                for span, span_group in AnnoTier(geoname.spans)\
                    .group_spans_by_containing_span(article['sections_to_ignore'],
                                                    allow_partial_containment=True)]):
                print("ignoring:", geoname['name'])
                continue
            feature_vectors.append(feature.values())
            geonameid = str(geoname['geonameid'])
            if geonameid in gold_locations:
                used_gold_locations |= set([geonameid])
                labels.append(True)
            else:
                labels.append(False)
        print("unused gold locations:", gold_locations - used_gold_locations)
    # L1 regularization helps with overfitting by constraining the model
    # to use fewer variables.
    clf = LogisticRegression(penalty='l1')
    clf.fit(feature_vectors, labels)
    predictions = clf.predict_proba(feature_vectors)
    print(sklearn.metrics.precision_recall_fscore_support(
            np.array(labels),
            predictions[:,1] > 0.5,
            average='micro'))
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
    # Remove overlapping gold spans favoring the ignored ones and geospans
    tag_values = {
        'ignore': 100,
        'geo': 1
    }
    doc.tiers['tags'].optimal_span_set(
        prefer=lambda span: tag_values.get(span.tag_name, 0))
    p['content'] = doc.text
    if 'geonameids' not in p:
        p['geonameids'] = set([
            span.attrs['id'] for span in doc.tiers['tags'].spans
            if span.tag_name == 'geo'])
    p['sections_to_ignore'] = AnnoTier([
        span for span in doc.tiers['tags'].spans
        if span.tag_name == 'ignore'])
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
