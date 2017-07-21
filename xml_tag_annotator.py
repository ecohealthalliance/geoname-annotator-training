#!/usr/bin/env python
from epitator.annotator import AnnoSpan, AnnoTier
from bs4 import BeautifulSoup, NavigableString
from lazy import lazy

class XMLTagSpan(AnnoSpan):

    def __init__(self, start, end, doc, label, element):
        self.start = start
        self.end = end
        self.doc = doc
        self.label = label
        self.element = element

    @lazy
    def tag_name(self):
        return self.element.name

    @lazy
    def attrs(self):
        return self.element.attrs

class XMLTagAnnotator:

    def __init__(self):
        pass

    def annotate(self, doc):
        # Need to run this first before other annotators because it strips tags
        # and transforms the text
        soup = BeautifulSoup(doc.text, 'html.parser')
        def traverse(element, clean_content, spans):
            if isinstance(element, NavigableString):
                clean_content += unicode(element)
            else:
                start = len(clean_content)
                for child in element.children:
                    clean_content, spans = traverse(child, clean_content, spans)
                end = len(clean_content)
                spans.append(XMLTagSpan(start, end, doc,
                      element.attrs.get('id'), element))
            return clean_content, spans
        clean_content = ""
        spans = []
        for child in soup.children:
            clean_content, spans = traverse(child, clean_content, spans)
        doc.text = clean_content
        doc.tiers['tags'] = AnnoTier(spans)
        return doc