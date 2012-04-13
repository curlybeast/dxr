#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# The MIT License
#
# Copyright (c) 2012 Taras Glek <tglek@mozilla.com>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# Author: Martyn Russell <martyn@lanedo.com>
#

import sys, os, errno
import optparse
from subprocess import call
from string import Template

# Define parameters:
#
# NOTE: prefix MUST be writeable,
# NOTE: the following are set by default by the option parser:
#       - prefix
#       - web_prefix
#       - hostname
#
prefix = ''
srcdir = ''
builddir = ''
web_prefix = ''
hostname = ''
buildenv = os.environ

def mkdir_p(path):
    try:
        os.makedirs(path)
#   except OSError as exc: # Python >2.5
#       if exc.errno == errno.EEXIST:
#           pass
#       else:
#           raise
    except OSError:
        pass

def which(program, env):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in env["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

def print_documentation():
    print '''
Generally to use DXR for your project from a blank canvas, you need to
do the following:

1. Run the --bootstrap command.

   This will ensure you have the directories and conditions set up to
   start building your project. This includes a prefix which all
   source directory is contained within and a build directory where
   all your sources are indexed into by DXR. There is also a web
   prefix which is the location of your Apache (or other) website HTML
   directory. This must be in place for the final indexing stage, but
   the bootstrap command ensures it exists and can be written to.

   The next part is to build LLVM and CLANG and install them into the
   prefix. This is what Mozilla use for mozilla-central and CLANG
   offers more information about C and C++ projects which we export
   through the web interface. A part of this is to build the cxx-clang
   plugin in the DXR source directory. The bootstrap command will git
   clone and build all of the sources you need here and install them.
   So prefix *must* be writeable.

2. Run the --new-config command.

   This creates the config which DXR uses for all operational
   purposes, e.g. to index your project, to store the database with
   the indexed information, how to update your project from the
   original repository, etc.

3. Run the --sanity-check command (optional).

   This ensures the prefix and other locations you're using actually
   are usable (i.e. writeable). It will also check the bootstrap stage
   worked and the necessary commands are in place to index your
   project.

4. Run the --shell command. (NOT AVAILABLE YET)

   This sets up your environment so LLVM/CLANG are used to build your
   project. Once in the shell you need to build your project,
   typically using:

     ./configure --prefix=$prefix (e.g. /opt/dxr)

5. Run the --index command. (NOT AVAILABLE YET)

   This indexes your built sources and creates a database according to
   the configutation we created in step #2.

There will be more information here to come, but this is the basic
concept of work flow to get your project indexed by DXR.

'''

def print_environment():
    print '--- Prefix     = %s' % (prefix)
    print '--- Source     = %s' % (srcdir)
    print '--- Build      = %s' % (builddir)
    print
    print '--- Web prefix = %s' % (web_prefix)
    print '--- Hostname   = %s' % (hostname)
    print
    print '--- PATH       = %s' % (buildenv["PATH"])
    print

def cmd_new_config(name, srcdir, builddir, web_prefix, hostname):
    # Creates a .config file in XDG locations by default,
    #   e.g. $HOME/.config/dxr/$NAME
    #
    # TODO: Need to check what type of repository we use and change
    #       the pullcommand and revision settings accordingly.

    template = '''
[DXR]
templates=$srcdir/dxr/templates
dxrroot=$srcdir/dxr

[Web]
wwwdir=$web_prefix
virtroot=
hosturl=$hostname

[$name]
sourcedir=$srcdir/$name
objdir=$builddir/$name
revision=git rev-parse HEAD $srcdir/$name
pullcommand=git pull --rebase
buildcommand=make
'''

    # Check dir exists
    dirname = os.path.join(os.environ['HOME'], '.config', 'dxr')
    mkdir_p(dirname)

    # TODO: Check if it already exists!?!

    # Create final article
    filename = os.path.join(dirname, name + '.config')
    print '--> Creating config file: %s' % (filename)

    f = open(filename, 'w')
    t = Template(template)
    content = t.substitute(locals())
    f.write(content)
    f.close()
    print '<-- Done'

def cmd_bootstrap():
    # Commands:
    #   mkdir -p /opt/dxr/source && cd /opt/dxr/source
    #   git clone http://llvm.org/git/llvm.git
    #   cd llvm
    #   git checkout release_30
    #   cd tools
    #   git clone http://llvm.org/git/clang.git
    #   cd clang
    #   git checkout release_30
    #   cd /opt/dxr/source/llvm
    #   ./configure --enable-optimized --enable-targets=x86,x86_64 --enable-assertions --prefix=/opt/dxr/
    #   make | egrep -v "argument unused during compilation|'linker' input unused when"
    #   make install
    #   cd /opt/dxr/source
    #   git clone https://github.com/garnacho/dxr.git # git://github.com/kalikiana/dxr.git
    #   git checkout lanedo-changes
    #   PATH="/opt/dxr/bin/:$PATH"
    #   cd /opt/dxr/source/dxr/xref-tools/cxx-clang
    #   make

    print '--> Bootstrapping DXR...'

    print '--> Creating source dir: %s' % (srcdir)
    mkdir_p(srcdir)

    print '--> Creating build dir: %s' % (builddir)
    mkdir_p(builddir)

    # Check exists!?
    rc=0

    print '--> Cloning LLVM'
    rc = call('git clone http://llvm.org/git/llvm.git', shell=True, cwd=srcdir)
    if rc:
        return rc

    llvmdir = os.path.join(srcdir, 'llvm')

    print '--> Changing branch to "release_30"'
    rc = call("git checkout release_30", shell=True, cwd=llvmdir)
    if rc:
        return rc

    toolsdir = os.path.join(llvmdir, 'tools')

    print '--> Cloning CLANG'
    rc = call('git clone http://llvm.org/git/clang.git', shell=True, cwd=toolsdir)
    if rc:
        return rc

    clangdir = os.path.join(toolsdir, 'clang')

    print '--> Changing branch to "release_30"'
    rc = call("git checkout release_30", shell=True, cwd=clangdir)
    if rc:
        return rc

    print '--> Configuring LLVM'
    rc = call("./configure --enable-optimized --enable-targets=x86,x86_64 --enable-assertions --prefix=%s" % (prefix), shell=True, cwd=llvmdir)
    if rc:
        return rc

    print '--> Building LLVM'
    rc = call("make", shell=True, cwd=llvmdir)
    if rc:
        return rc

    print '--> Installing LLVM'
    rc = call("make install", shell=True, cwd=llvmdir)
    if rc:
        return rc

    print '--> Cloning DXR'
    rc = call('git clone https://github.com/garnacho/dxr.git', shell=True, cwd=srcdir)
    if rc:
        return rc

    dxrdir = os.path.join(srcdir, 'dxr')

    print '--> Changing branch to "lanedo-changes"'
    rc = call("git checkout lanedo-changes", shell=True, cwd=dxrdir)
    if rc:
        return rc

    cxxdir = os.path.join(dxrdir, 'xref-tools', 'cxx-clang')

    print '--> Building DXR cxx-clang plugin'
    rc = call("make", shell=True, cwd=cxxdir, env=buildenv)
    if rc:
        return rc

    print '<-- Done'
    return 0

def cmd_sanity_check():
     # Sanity check environment:
     #   Check $prefix exists + is writeable
     #   Check $srcdir exists + is writeable
     #   Check $builddir exists + is writeable
     #   Check $web_prefix exists + is writeable
     #   Check llvm-config is executable (i.e. in path)
     #
     print '--> Sanity checking set up...'
     print '-->   Checking locations exist and have correct permissions:'
     print '-->     %s Prefix (%s)' % ('[Yes]' if os.access(prefix, os.W_OK) else '[No] ', prefix)
     print '-->     %s Source (%s)' % ('[Yes]' if os.access(srcdir, os.W_OK) else '[No] ', srcdir)
     print '-->     %s Build (%s)' % ('[Yes]' if os.access(builddir, os.W_OK) else '[No] ', builddir)
     print '-->     %s Web Prefix (%s)' % ('[Yes]' if os.access(web_prefix, os.W_OK) else '[No] ', web_prefix)

     print '-->   Checking binaries:'

     rc = which('llvm-config', buildenv)
     print '-->     %s llvm-config (%s)' % ('[Yes]' if rc != None else '[No] ', rc)

     print
     print '<-- Done'
     return 0

def main(args):
    if hasattr(os, 'getuid') and os.getuid() == 0:
        sys.stderr.write('You should not run %prog as root.\n')
        sys.exit(1)

    usage = '%s command [ options ... ]\n' \
            '%s --help' % (sys.argv[0], sys.argv[0])

    parser = optparse.OptionParser(usage,
				   add_help_option=True,
				   description='DXR source code indexer')

    # Locations options
    group = optparse.OptionGroup(parser,
				 'Location Options',
				 'Used for prefix configurations')
    group.add_option('-p', '--prefix',
		     metavar="PATH",
		     dest='prefix',
		     default=os.path.join('/', 'opt', 'dxr'),
		     help='Sets the prefix to use before issuing any commands [default = %default]')
    group.add_option('-w', '--web-prefix',
		     metavar="PATH",
		     dest='web_prefix',
		     default=os.path.join('/', 'srv', 'dxr', 'html'),
		     help='Sets the prefix for the website location [default = %default]')
    group.add_option('-n', '--hostname',
		     metavar="HOST",
		     dest='hostname',
		     default='http://localhost',
		     help='Sets the hostname to use in the config for the website [default = %default]')
    parser.add_option_group(group)

    # Debug options
    group = optparse.OptionGroup(parser,
				 'Debug Options',
				 'Used to follow the script more closely')
    group.add_option('-e', '--print-environment',
		     action='count',
		     dest='print_environment',
		     help='Prints prefixes, directories and useful information used before operations')
    parser.add_option_group(group)

    # Main commands
    parser.add_option('-i', '--documentation',
                      action='count',
                      dest='documentation',
                      help='Explains the process of creating a DXR set up and how to use this command')
    parser.add_option('-b', '--bootstrap',
                      action='count',
                      dest='bootstrap',
                      help='Builds and installs LLVM & CLANG. Also sets up prefixes and paths')
    parser.add_option('-s', '--sanity-check',
                      action='count',
                      dest='sanity_check',
                      help='Checks the current set up is sane')
    parser.add_option('-c', '--new-config',
                      metavar="NAME",
                      dest='new_config',
                      help='Creates a new DXR config file for a project')

    options, args = parser.parse_args(args)

    # Set globals
    global prefix, srcdir, builddir, web_prefix, hostname, buildenv
    prefix = options.prefix
    srcdir = os.path.join(prefix, 'source')
    builddir = os.path.join(prefix, 'build')
    web_prefix = options.web_prefix
    hostname = options.hostname
    buildenv["PATH"] = os.path.join(prefix, 'bin') + ":" + buildenv["PATH"]

    # Do something...
    if options.documentation:
        print_documentation()
        sys.exit(0)

    if options.print_environment:
        print_environment()

    if options.bootstrap:
        rc = cmd_bootstrap()
        if rc:
            sys.exit(rc)

    if options.sanity_check:
        rc = cmd_sanity_check()
        if rc:
            sys.exit(rc)

    if options.new_config:
        rc = cmd_new_config(options.new_config, srcdir, builddir, web_prefix, hostname)
        if rc:
            sys.exit(rc)

    if not options.documentation and \
       not options.new_config and not options.sanity_check and \
       not options.bootstrap and not options.print_environment:
        print 'Expected command'
        print
        print usage
        rc = -1
    else:
        rc = 0

    sys.exit(rc)

# Start
main(sys.argv)
