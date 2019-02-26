from epitator.get_database_connection import get_database_connection
from collections import defaultdict
import sqlite3


connection = get_database_connection()
connection.row_factory = sqlite3.Row
cursor = connection.cursor()

# ADM geonames are considered equivalent to the geonames they directly contain and
# share a name with.
# Indirect containment makes false positives more likely (Mexico and Mexico City)
# There are still false positives for things like schools.
# http://www.geonames.org/6784866/pesantren.html
# Island of Hawaii
result = cursor.execute('''
SELECT
alternatename_lemmatized,
g1.*,
g2.geonameid AS geoname2,
g2.asciiname AS asciiname2
FROM alternatenames a1
INNER JOIN alternatenames a2 USING ( alternatename_lemmatized )
INNER JOIN geonames g1 ON a1.geonameid = g1.geonameid
INNER JOIN geonames g2 ON  a2.geonameid = g2.geonameid
WHERE g1.feature_code LIKE 'ADM%' AND g1.geonameid != g2.geonameid AND
g1.country_code = g2.country_code AND g1.admin1_code = g2.admin1_code AND
g1.admin2_code = g2.admin2_code AND g1.admin3_code = g2.admin3_code
''')
geonameid_to_equivalents = defaultdict(set)
for item in result:
    direct_containment = item['feature_code'].startswith('ADM1') and not item['admin2_code']
    direct_containment |= item['feature_code'].startswith('ADM2') and not item['admin3_code']
    direct_containment |= item['feature_code'].startswith('ADM3') and not item['admin4_code']
    direct_containment |= item['feature_code'].startswith('ADM4') and not item['admin4_code']
    if direct_containment:
        if item['alternatename_lemmatized'] in item['asciiname2'].lower() and item['alternatename_lemmatized'] in item['asciiname'].lower():
            geonameid_to_equivalents[item['geonameid']].add(item['geoname2'])
            geonameid_to_equivalents[item['geoname2']].add(item['geonameid'])

def expand_geoname_id(geonameid):
    return geonameid_to_equivalents[geonameid] | set([geonameid])
