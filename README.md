This directory contains scripts to train and score the accuracy of the EpiTator
geoname annotator.


# Usage

download_annotations.py - Downlaod geoannotated documents into `resolved_geoannoated_data`.
The source documents come from the [American National Corpus](http://www.anc.org/)


train.py - Train a geoname classifier using the files from `resolved_geoannoated_data`
and output it as standalone python module called geoname_classifier.py


score.py - Score the performance of the geoname_classifier.py file in this directory
