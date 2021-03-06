#!/usr/bin/env python2

import os
import dxr
import cgi
import itertools
import sys
import subprocess
from ConfigParser import ConfigParser

class HtmlBuilder:
  def _zipper(self, func):
    """ Returns all contents from all plugins. """
    if func not in self.resmap:
      return []
    return itertools.chain(*[f(self.blob.get(name, None), self.filepath, self.tree, self.conn)
      for name, f in self.resmap[func]])

  def __init__(self, tree, filepath, dstpath, blob, resmap, conn = None):
    # Read and expand all templates
    self.html_header = tree.getTemplateFile("dxr-header.html")
    self.html_footer = tree.getTemplateFile("dxr-footer.html")
    self.html_sidebar_header = tree.getTemplateFile("dxr-sidebar-header.html")
    self.html_sidebar_footer = tree.getTemplateFile("dxr-sidebar-footer.html")
    self.html_main_header = tree.getTemplateFile("dxr-main-header.html")
    self.html_main_footer = tree.getTemplateFile("dxr-main-footer.html")
    
    self.source = dxr.readFile(filepath)
    self.virtroot = tree.virtroot
    self.treename = tree.tree
    self.filename = os.path.basename(filepath)
    self.filepath = filepath
    self.srcroot = tree.sourcedir
    self.dstpath = os.path.normpath(dstpath)
    self.srcpath = filepath.replace(self.srcroot + '/', '')
    self.show_sidebar = False

    self.blob = blob
    self.resmap = resmap
    self.tree = tree
    self.conn = conn

    # Config info used by dxr.js
    self.globalScript = ['var virtroot = "%s", tree = "%s";' % (self.virtroot, self.treename)]

  def getSidebarActions(self):
    html = ''
    blameLinks = { \
      'Log': 'http://hg.mozilla.org/mozilla-central/filelog/$rev/$filename', \
      'Blame': 'http://hg.mozilla.org/mozilla-central/annotate/$rev/$filename', \
      'Diff': 'http://hg.mozilla.org/mozilla-central/diff/$rev/$filename', \
      'Raw': 'http://hg.mozilla.org/mozilla-central/raw-diff/$rev/$filename' }
    html+=('<div id="sidebarActions"><b>Actions</b>\n')
    # Pick up revision command and URLs from config file
    source_dir = self.srcroot
    if 'revision' in globals():
      revision = globals()['revision']
    else:
      try:
        revision_command = self.tree.getOption('revision')
        revision_command = revision_command.replace('$source', source_dir)
        revision_process = subprocess.Popen ([revision_command], stdout=subprocess.PIPE, shell=True)
        revision = revision_process.stdout.readline().strip()
      except:
        if not 'config-notice' in globals():
          globals()['config-notice'] = True
          msg = sys.exc_info()[1] # Python 2/3 compatibility
          print '\033[93mError: %s\033[0m' % msg
        revision = ''
      globals()['revision'] = revision
    if revision == '':
      blameLinks = {}
    for link in blameLinks:
      try:
        customLink = self.tree.getOption(link)
      except:
        if not 'log-notice' + link in globals():
          globals()['log-notice' + link] = True
          print '\033[93mNotice: Missing %s config key\033[0m' % link
        customLink = blameLinks[link]
      realLink = customLink \
        .replace('$rev', revision) \
        .replace('$filename', self.srcpath)
      html+=('<a href="%s">%s</a> &nbsp;\n' % (realLink, link))
    html+=('</div>')
    return html

  def toHTML(self, inhibit_sidebar):
    out = open(self.dstpath, 'w')
    sidebarActions = self.getSidebarActions()
    self.html_header = self.html_header.replace('${sidebarActions}', sidebarActions);

    if inhibit_sidebar is True:
      str = 'false'
    else:
      str = 'true'
    self.html_header = self.html_header.replace('${showLeftSidebar}', str)

    out.write(self.html_header + '\n')
    self.writeSidebar(out)
    self.writeMainContent(out)
    self.writeGlobalScript(out)
    out.write(self.html_footer + '\n')
    out.close()

  def writeSidebar(self, out):
    sidebarElements = [x for x in self._zipper("get_sidebar_links")]
    if len(sidebarElements) == 0: return

    out.write(self.html_sidebar_header + '\n')
    self.writeSidebarBody(out, sidebarElements)
    out.write(self.html_sidebar_footer + '\n')

  def writeSidebarBody(self, out, elements):
    containers = {}
    for e in elements:
      containers.setdefault(len(e) > 4 and e[4] or None, []).append(e)

    # Sort the containers by their location
    # Global scope goes last, and scopes declared outside of this file goes
    # before everything else
    clocs = { None: 2 ** 32 }
    for e in elements:
      if e[0] in containers:
        clocs[e[0]] = int(e[1])
    contKeys = containers.keys()
    contKeys.sort(lambda x, y: cmp(clocs.get(x, 0), clocs.get(y, 0)))

    for cont in contKeys:
      if cont is not None:
        out.write('<b>%s</b>\n<div>\n' % cgi.escape(str(cont)))
      #containers[cont].sort(lambda x, y: int(x[1]) - int(y[1]))
      containers[cont].sort(lambda x, y: cmp(x[0], y[0]))
      for e in containers[cont]:
        img = len(e) > 3 and e[3] or "images/icons/page_white_code.png"
        title = len(e) > 2 and e[2] or e[0]
        out.write('<img src="%s/%s" class="sidebarimage">' % (self.virtroot, img))
        out.write('<a class="sidebarlink" title="%s" href="#l%d">%s</a><br>\n' %
          (cgi.escape(title), int(e[1]), cgi.escape(e[0])))
      if cont is not None:
        out.write('</div><br />\n')

  def writeMainContent(self, out):
    out.write(self.html_main_header)
    self.writeMainBody(out)
    out.write(self.html_main_footer)

  def writeMainBody(self, out):
    # So, we have a minor issue with writing out the main body. Some of our
    # information is (line, col) information and others is file offset. Also,
    # we don't necessarily have the information in sorted order. This means we
    # have to hope that all ranges are in a strict tree hierarchy, otherwise
    # things will blow up.
    syntax_regions = self._zipper("get_syntax_regions")
    links = self._zipper("get_link_regions")
    line_notes = self._zipper("get_line_annotations")

    if self.source is None:
      return

    # Blow the contents of the file up into an array; we escape the source and
    # build the line map at the same time.
    line_map = [0]
    closure = ['', 0]
    def handle_char(x):
      if x == '\n':
        line_map.append(closure[1])
      elif closure[0] == '\r':
        line_map.append(closure[1] - 1)
      closure[0] = x
      closure[1] += 1
      return cgi.escape(x)
    chars = [handle_char(x) for x in self.source]
    chars.append('')

    def off(val):
      if isinstance(val, tuple):
        return line_map[val[0] - 1] + val[1]
      return val
    # Produce all of the syntax regions and links. Sincerely hope that the two
    # do not produce partially-overlapping results.
    for syn in syntax_regions:
      if syn[0] is None or syn[1] is None:
        continue
      chars[off(syn[0])] = '<span class="%s">%s' % (syn[2], chars[off(syn[0])])
      chars[off(syn[1]) - 1] += '</span>'

    href_prefix = self.virtroot + "/search.cgi?tree=" + self.treename + '&string='

    for link in links:
      if link[0] is None or link[1] is None:
        continue
      item = self.source[off(link[0]):off(link[1])]
      chars[off(link[0])] = '<a aria-haspopup="true" href="%s%s" %s>%s' % (
        href_prefix, item,
        ' '.join([attr + '="' + str(link[2][attr]) + '"' for attr in link[2]]),
        chars[off(link[0])])
      chars[off(link[1]) - 1] += '</a>'

    # Use the line annotations to build a map of the gutter annotations.
    line_mods = [[num + 1, ''] for num in xrange(len(line_map))]
    for l in line_notes:
      line_mods[l[0] - 1][1] += ' ' + ' '.join(
        [attr + '="' + str(l[1][attr]) + '"' for attr in l[1]])
    line_divs = ['<div%s id="l%d"><a class="ln" href="#l%d">%d</a></div>' %
      (mod[1], mod[0], mod[0], mod[0]) for mod in line_mods]

    # Okay, finally, combine everything together into the file.
    out.write('<div id="linenumbers">%s</div><div id="code">%s</div>' %
      (''.join(line_divs), ''.join(chars)))

  def writeGlobalScript(self, out):
    """ Write any extra JS for the page. Lines of script are stored in self.globalScript."""
    # Add app config info
    out.write('<script type="text/javascript">')
    out.write('\n'.join(self.globalScript))
    out.write('</script>')


# HTML-ifier map
# The keys are the endings of files to match
# First set of values are {funcname, [funclist]} dicts
# funclist is the lists of functions to apply, as a (plugin name, func) tuple

htmlifier_map = {}
ending_iterator = []
inhibit_sidebar = {}

def build_htmlifier_map(plugins):
  def add_to_map(ending, hmap, pluginname, append):
    for x in ['get_sidebar_links', 'get_link_regions', 'get_line_annotations',
        'get_syntax_regions']:
      if x not in hmap:
        continue
      details = htmlifier_map[ending].setdefault(x, [None])
      if append:
        details.append((pluginname, hmap[x]))
      else:
        details[0] = (pluginname, hmap[x])

    if 'get_inhibit_sidebar' in hmap and hmap['get_inhibit_sidebar'] is True:
      inhibit_sidebar[ending] = True

  # Add/append details for each map
  for plug in plugins:
    plug_map = plug.get_htmlifiers()
    for ending in plug_map:
      if ending not in htmlifier_map:
        ending_iterator.append(ending)
        htmlifier_map[ending] = {}
      nosquash = 'no-override' in plug_map[ending]
      add_to_map(ending, plug_map[ending], plug.__name__, nosquash)
  # Sort the endings by maximum length, so that we can just find the first one
  # in the list
  ending_iterator.sort(lambda x, y: cmp(len(y), len(x)))

def make_html(srcpath, dstfile, treecfg, blob, conn = None):
  # Match the file in srcpath
  result_map = {}
  signalStop = False
  inhibit = False

  for end in ending_iterator:
    if srcpath.endswith(end):
      for func in htmlifier_map[end]:
        reslist = result_map.setdefault(func, [None])
        flist = htmlifier_map[end][func]
        reslist.extend(flist[1:])
        if flist[0] is not None:
          reslist[0] = flist[0]
          signalStop = True
      if end in inhibit_sidebar:
        inhibit = True
    if signalStop:
      break
  builder = HtmlBuilder(treecfg, srcpath, dstfile, blob, result_map, conn)
  builder.toHTML(inhibit)
