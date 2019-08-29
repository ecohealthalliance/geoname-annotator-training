This directory contains scripts to train and score the accuracy of the EpiTator
geoname annotator.


# Usage

Run the scripts in this order:

`GEONAME_CURATOR_URL=https://geoname-curator.eha.io python download_annotations.py` - Download geoannotated documents from the geoname-curator instance at GEONAME_CURATOR_URL into `resolved_geoannoated_data`.
The resolved_geoannoated_data already included in this repository comes from the [American National Corpus](http://www.anc.org/)

`python train.py` - Train a geoname classifier using the files from `resolved_geoannoated_data`
and output it as standalone python module called geoname_classifier.py

`python score.py `- Score the performance of the geoname_classifier.py file in this directory

Once an acceptable geoname_classifier.py has been trained, it can be used with EpiTator by replacing the file with the same name in the epitator directory.
