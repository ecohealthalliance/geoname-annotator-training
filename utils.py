from epitator.annotator import AnnoTier
from epitator.geoname_annotator import location_contains

def combine_geotags(tags, geonames_by_id):
    # Remove overlapping gold spans favoring the ignored ones and geospans
    tag_values = {
        'ignore': 100,
        'geo': 0
    }
    tag_chains = AnnoTier(
        tag for tag in tags if tag.tag_name != 'ignore').chains(at_least=2, at_most=4, max_dist=2)
    combined_tags = []
    for tag_chain in tag_chains:
        tag_chain_geonames = [geonames_by_id.get(tag.label) for tag in tag_chain.iterate_leaf_base_spans()]
        prev_span = None
        valid_chain = True
        for span in tag_chain.iterate_leaf_base_spans():
            if prev_span:
                gap = span.doc.text[prev_span.end:span.start]
                if '.' in gap:
                    valid_chain = False
                    break
                # Only merge matching geonames if they are adjacent.
                elif prev_span.label == span.label and gap != "":
                    valid_chain = False
                    break
            prev_span = span
        innermost_geoname = None
        for geoname in tag_chain_geonames:
            if not valid_chain:
                break
            if not innermost_geoname or location_contains(innermost_geoname, geoname):
                innermost_geoname = geoname
            for other_geoname in tag_chain_geonames:
                if geoname == other_geoname:
                    pass
                elif location_contains(other_geoname, geoname):
                    pass
                elif location_contains(geoname, other_geoname):
                    pass
                else:
                    valid_chain = False
                    break
        if valid_chain:
            tag_chain.label = innermost_geoname['geonameid']
            tag_chain.attrs = {
                'id': innermost_geoname['geonameid']
            }
            tag_chain.tag_name = 'geo'
            combined_tags.append(tag_chain)

    result = AnnoTier(tags.spans + combined_tags).optimal_span_set(
        prefer=lambda span: (tag_values.get(span.tag_name, 0), len(span), -1,))
    return result
