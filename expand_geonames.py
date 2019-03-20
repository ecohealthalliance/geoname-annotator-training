from epitator.get_database_connection import get_database_connection
from collections import defaultdict
import sqlite3
import os

EXPANDED_GEONAME_DB_PATH = ".geoname_expansions.sqlitedb"

db_exists = os.path.exists(EXPANDED_GEONAME_DB_PATH)

expanded_geoname_db_connection = sqlite3.connect(EXPANDED_GEONAME_DB_PATH)
expanded_geoname_db_connection.row_factory = sqlite3.Row
expanded_geoname_db_cur = expanded_geoname_db_connection.cursor()

if not db_exists:
    expanded_geoname_db_cur.execute('''CREATE TABLE equivalent_geonames
        (geonameid TEXT, equivalent_geonameid TEXT,
         PRIMARY KEY (geonameid, equivalent_geonameid))''')

    epitator_connection = get_database_connection()
    epitator_connection.row_factory = sqlite3.Row
    epitator_cursor = epitator_connection.cursor()
    # ADM geonames are considered equivalent to the geonames they directly contain 
    # (have matching adm[1-4] properties) and share a name with.
    # Indirect containment makes false positives more likely (e.g. Mexico and Mexico City)
    # The following query finds pairs of matching lemmatized alternate names
    # that correspond to distinct geonames with matching admin codes.
    result = epitator_cursor.execute('''
    SELECT
    alternatename_lemmatized,
    g1.*,
    g2.geonameid AS geoname2,
    g2.asciiname AS asciiname2
    FROM alternatenames a1
    INNER JOIN alternatenames a2 USING ( alternatename_lemmatized )
    INNER JOIN geonames g1 ON a1.geonameid = g1.geonameid
    INNER JOIN geonames g2 ON  a2.geonameid = g2.geonameid
    WHERE g1.feature_code LIKE 'ADM%' AND
    g2.feature_class NOT IN ('S', 'R') AND
    g1.geonameid != g2.geonameid AND
    g1.country_code = g2.country_code AND
    g1.admin1_code = g2.admin1_code AND
    g1.admin2_code = g2.admin2_code AND
    g1.admin3_code = g2.admin3_code AND
    g1.admin4_code = g2.admin4_code
    ''')
    geonameid_to_equivalents = defaultdict(set)
    equivalent_geoname_insert_command = 'INSERT OR IGNORE INTO equivalent_geonames VALUES (?, ?)'
    for item in result:
        direct_containment = item['feature_code'].startswith('ADM1') and not item['admin2_code']
        direct_containment |= item['feature_code'].startswith('ADM2') and not item['admin3_code']
        direct_containment |= item['feature_code'].startswith('ADM3') and not item['admin4_code']
        direct_containment |= item['feature_code'].startswith('ADM4')
        if direct_containment:
            name1 = item['asciiname'].lower()
            name2 = item['asciiname2'].lower()
            if name1 in name2 or name2 in name1:
                expanded_geoname_db_cur.executemany(equivalent_geoname_insert_command, [
                    (item['geonameid'], item['geoname2'],),
                    (item['geoname2'], item['geonameid'],),
                    ])
    expanded_geoname_db_connection.commit()
    expanded_geoname_db_cur.execute("CREATE INDEX equivalent_geonameids ON equivalent_geonames (geonameid)")
    expanded_geoname_db_connection.commit()

def expand_geoname_id(geonameid):
    results = expanded_geoname_db_cur.execute('''
        SELECT equivalent_geonameid
        FROM equivalent_geonames
        WHERE geonameid = ?
    ''', (geonameid,))
    result_set = set([r['equivalent_geonameid'] for r in results])
    return result_set | set([geonameid])
