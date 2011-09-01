"""
  Module
"""
# -*- coding: utf-8 -*-
import ConfigParser
import json
import os
import random
import re
import string
import sys

import jsbridge

from docutils import nodes
from docutils.parsers.rst import Directive, directives, roles
from docutils.transforms import TransformError, Transform
from docutils.utils import ExtensionOptionError
from docutils.nodes import fully_normalize_name as normalize_name

from itertools import chain, dropwhile, islice, takewhile

import zotero4rst.jsonencoder
from zotero4rst.util import html2rst, unquote

class smallcaps(nodes.Inline, nodes.TextElement): pass
roles.register_local_role("smallcaps", smallcaps)

DEFAULT_CITATION_FORMAT = "http://www.zotero.org/styles/chicago-author-date"

# placeholder for global bridge to Zotero
zotero_conn = None;

# verbose flag
verbose_flag = False

def z4r_debug(what):
    if verbose_flag == 1:
        sys.stderr.write("%s\n"%(what))

def check_zotero_conn():
    if not zotero4rst.zotero_conn:
        ## A kludge, but makes a big noise about the extension syntax for clarity.
        sys.stderr.write("#####\n")
        sys.stderr.write("##\n")
        sys.stderr.write("##  Must set zotero-setup:: directive before zotero:: directive is used.\n")
        sys.stderr.write("##\n")
        sys.stderr.write("#####\n")
        raise ExtensionOptionError("must set zotero-setup:: directive before zotero:: directive is used.")

class ZoteroConnection(object):
    def __init__(self, **kwargs):
        self.bibType = kwargs.get('bibType', DEFAULT_CITATION_FORMAT)
        self.firefox_connect()
        self.zotero_resource()
        self.tracked_items = []
        self.cite_pos = 0
        self.keys = ConfigParser.SafeConfigParser()
        self.keys.optionxform = str
        self.items_registered = False

    def load_keyfile(self, path):
        self.keys.read(os.path.relpath(path))

    def track_item(self, item):
        self.tracked_items.append(item)

    def firefox_connect(self):
        self.back_channel, self.bridge = jsbridge.wait_and_create_network("127.0.0.1", 24242)
        self.back_channel.timeout = self.bridge.timeout = 60

    def zotero_resource(self):
        self.methods = jsbridge.JSObject(self.bridge, "Components.utils.import('resource://csl/export.js')")

    def register_items(self):
        if not(self.items_registered):
            uniq_ids = list(set([ item.id for item in self.tracked_items ]))
            self.methods.registerItemIds(uniq_ids)

    def get_index(self, cite_info):
        return self.tracked_items.index(cite_info)

    def generate_rest_bibliography(self):
        """Generate a bibliography of reST nodes."""
        self.register_items()
        bibdata = unquote(json.loads(self.methods.getBibliographyData()))
        # XXX There is some nasty business here.
        #
        # Some nested nodes come out serialized when run through html2rst, so something
        # needs to be fixed there.
        #
        # More important, we need to figure out how to control formatting
        # in the bib -- hanging indents especially. Probably the simplest thing
        # is just to set some off-the-shelf named style blocks in style.odt, and
        # apply them as more or less appropriate.
        #
        return html2rst("%s%s%s"%(bibdata[0]["bibstart"], "".join(bibdata[1]), bibdata[0]["bibend"]))

    def lookup_key(self, key):
        if self.keys.has_option('keys', key):
            return self.keys.get('keys', key)
        else:
            return None

    def get_citation(self, cite_info):
        self.register_items()
        citation = { 'citationItems' : [cite_info],
                     'properties'    : { 'index'    : zotero_conn.get_index(cite_info),
                                         'noteIndex': cite_info.note_index } }
        res = self.methods.getCitationBlock(citation)
        return html2rst(unquote(res))

class ZoteroSetupDirective(Directive):
    def __init__(self, *args, **kwargs):
        Directive.__init__(self, *args)
        # This is necessary: connection hangs if created outside of an instantiated
        # directive class.
        zotero4rst.zotero_conn = ZoteroConnection()
        zotero4rst.verbose_flag = self.state_machine.reporter.report_level

    required_arguments = 0
    optional_arguments = 0
    has_content = False
    option_spec = {'format' : directives.unchanged,
                   'keyfile': directives.unchanged }
    def run(self):
        if self.options.has_key('keyfile'):
            zotero_conn.load_keyfile(self.options['keyfile'])
        z4r_debug("=== Zotero4reST: Setup run #1 (establish connection, spin up processor) ===")
        zotero_conn.methods.instantiateCiteProc(self.options.get('format', DEFAULT_CITATION_FORMAT))
        return []

class ZoteroTransform(Transform):
    default_priority = 650
    # Bridge hangs if output contains above-ASCII chars (I guess Telnet kicks into
    # binary mode in that case, leaving us to wait for a null string terminator)
    # JS strings are in Unicode, and the JS escaping mechanism for Unicode with
    # escape() is, apparently, non-standard. I played around with various
    # combinations of decodeURLComponent() / encodeURIComponent() and escape() /
    # unescape() ... applying escape() on the JS side of the bridge, and
    # using the following suggestion for a Python unquote function worked,
    # so I stuck with it:
    #   http://stackoverflow.com/questions/300445/how-to-unquote-a-urlencoded-unicode-string-in-python

    def apply(self):
        cite_info = self.startnode.details['cite_info']
        # get the footnote label
        footnote_node = self.startnode.parent.parent
        if type(footnote_node) == nodes.footnote:
            cite_info.note_index = int(str(footnote_node.children[0].children[0]))
        newnode = zotero_conn.get_citation(cite_info)
        self.startnode.replace_self(newnode)

class ZoteroBibliographyDirective(Directive):

    ## This could be extended to support selection of
    ## included bibliography entries. The processor has
    ## an API to support this, although it hasn't yet been
    ## implemented in any products that I know of.
    required_arguments = 0
    optional_arguments = 1
    has_content = False
    def run(self):
        z4r_debug("\n--- Zotero4reST: Bibliography #1 (placeholder set) ---")
        pending = nodes.pending(ZoteroBibliographyTransform)
        pending.details.update(self.options)
        self.state_machine.document.note_pending(pending)
        return [pending]

class ZoteroBibliographyTransform(Transform):

    default_priority = 700

    def apply(self):
        z4r_debug("\n--- Zotero4reST: Bibliography #2 (inserting content) ---")
        newnode = zotero4rst.zotero_conn.generate_rest_bibliography()
        self.startnode.replace_self(newnode)

class ZoteroCitationInfo(object):
    """Class to hold information about a citation for passing to Zotero."""
    def __init__(self, **kwargs):
        self.key = kwargs['key']
        newkey = zotero4rst.zotero_conn.lookup_key(self.key)
        if newkey is not None:
            self.origkey = self.key
            self.key = newkey
        self.id = int(zotero4rst.zotero_conn.methods.getItemId(self.key))
        self.label = kwargs.get('label', None)
        self.locator = kwargs.get('locator', None)
        self.suppress_author = kwargs.get('suppress_author', False)
        self.prefix = kwargs.get('prefix', None)
        self.suffix = kwargs.get('suffix', None)
        self.note_index = 0

def zot_parse_cite_string(cite_string):
    """Parse a citation string. This is inteded to be "pandoc-like".
Examples: `see @Doe2008` `also c.f. @Doe2010`
Returns an array of hashes with information."""

    KEY_RE = r'(-?)@([A-Za-z0-9_-]+),?'
    def is_key(s): return re.match(KEY_RE, s)
    def not_is_key(s): return not(is_key(s))
    def not_is_pipe(s): return s != '|'

    words = [ n for n in re.split(r"( |\|)", cite_string) if n != ' ' and n != '' ]
    raw_keys = [ word for word in words if is_key(word) ]
    if len(raw_keys) == 0:
        raise ExtensionOptionError("No key found in citation: '%s'."%(cite_string))
    elif len(raw_keys) > 1:
        raise ExtensionOptionError("Too many keys in citation: '%s'."%(cite_string))
    else:
        m = re.match(KEY_RE, raw_keys[0])
        key = m.group(2)
        suppress_author = (m.group(1) == '-')
        prefix = " ".join(takewhile(not_is_key, words))
        after_cite = tuple(islice(dropwhile(not_is_key, words), 1, None))
        suffix=None
        locator=None
        # suffix is separated by | for now
        locator = " ".join(takewhile(not_is_pipe, after_cite))
        suffix = " ".join(islice(dropwhile(not_is_pipe, after_cite), 1, None))
        return ZoteroCitationInfo(key=key,
                                  prefix=prefix,
                                  suffix=suffix,
                                  suppress_author=suppress_author,
                                  locator=locator)

def random_label():
    return "".join(random.choice(string.digits) for x in range(20))

def zot_cite_role(role, rawtext, text, lineno, inliner,
                  options={}, content=[]):
    check_zotero_conn()

    cite_info = zot_parse_cite_string(text)
    zotero4rst.zotero_conn.track_item(cite_info)
    if not(zotero4rst.zotero_conn.methods.isInTextStyle()):
        if type(inliner.parent) == nodes.footnote:
            # already in a footnote, just add a pending
            pending = nodes.pending(ZoteroTransform)
            pending.details['cite_info'] = cite_info
            inliner.document.note_pending(pending)
            return [pending], []
        else:
            # not in a footnote; insert a reference and add a footnote
            # to the end

            label = random_label()
            #refname = normalize_name(label)

            #pending = nodes.pending(ZoteroAppendFootnoteTransform)
            #pending.details['cite_info'] = cite_info
            #pending.details['label'] = label
            #inliner.document.note_pending(pending)

            refnode = nodes.footnote_reference('[%s]_' % label)
            refnode['auto'] = 1
            refnode['refname'] = label
            inliner.document.note_footnote_ref(refnode)
            inliner.document.note_autofootnote_ref(refnode)

            footnote = nodes.footnote("")
            footnote['auto'] = 1
            footnote['names'].append(label)
            pending = nodes.pending(ZoteroTransform)
            pending.details['cite_info'] = cite_info
            footnote += nodes.paragraph("", "", pending)
            inliner.document.note_pending(pending)
            inliner.document.note_autofootnote(footnote)
            where_to_add = inliner.parent
            while where_to_add is not None and \
                    not(isinstance(where_to_add, nodes.Structural)):
                where_to_add = where_to_add.parent
            if where_to_add is None: where_to_add = inliner.document
            where_to_add += footnote
            return [refnode], []
    else:
        pending = nodes.pending(ZoteroTransform)
        pending.details['cite_info'] = cite_info
        inliner.document.note_pending(pending)
        return [pending], []

# setup zotero directives
directives.register_directive('zotero-setup', ZoteroSetupDirective)
directives.register_directive('zotero-bibliography', ZoteroBibliographyDirective)
roles.register_canonical_role('zc', zot_cite_role)