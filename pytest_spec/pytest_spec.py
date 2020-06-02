# -*- coding: utf-8 -*-

import pytest
import time
import os


def pytest_addhooks(pluginmanager):
    from . import hooks
    pluginmanager.add_hookspecs(hooks)


def pytest_addoption(parser):
    group = parser.getgroup('spec')
    group.addoption('--spec',
                    action='store',
                    metavar='path',
                    dest='specpath',
                    default=None,
                    help='create test sepc file at given path.')

    parser.addini('HELLO', 'Dummy pytest.ini setting')


def pytest_configure(config):
    specpath = config.getoption('specpath')
    if specpath:
        if not hasattr(config, 'slaveinput'):
            # prevent opening htmlpath on slave nodes (xdist)
            config._spec = TestSpec(specpath, config)
            config.pluginmanager.register(config._spec)


def pytest_unconfigure(config):
    spec = getattr(config, '_spec', None)
    if spec:
        del config._spec
        config.pluginmanager.unregister(spec)


@pytest.fixture
def bar(request):
    return request.config.option.specpath


class TestSpec(object):
    def __init__(self, specfile, config):
        specfile = os.path.expanduser(os.path.expandvars(specfile))
        self.specfile = os.path.abspath(specfile)
        self.contents = []
        self.header = ["This is the header\n"]
        self.footer = ["This is the footer\n"]
        self.testSection = {}
        self.config = config

    def _generate_test_spec_content(self, config, items):
        stack = []
        indent = ""
        for item in items:
            needed_collectors = item.listchain()[1:]  # strip root node
            while stack:
                if stack == needed_collectors[:len(stack)]:
                    break
                stack.pop()
            for col in needed_collectors[len(stack):]:
                stack.append(col)
                key = self._get_name(col)
                if key == "()" or key in self.testSection:  # Skip Instances.
                    continue
                indent = (len(stack) - 1) * 4 * " "
                section_content = "{}{}\n".format(indent,
                                                  self._get_title(col, key))
                if hasattr(col, "_obj") and col._obj.__doc__:
                    for line in col._obj.__doc__.strip().splitlines():
                        section_content = section_content + "{}{}{}\n".format(
                            indent, 4 * " ", line.strip())
                self.testSection[key] = section_content
                self.contents.append(section_content)

    def _get_name(self, item):
        key = item.name
        if hasattr(item, "originalname") and item.originalname is not None:
            key = item.originalname
        return key

    def _get_title(self, item, key):
        #return "<%s %s>" % (item.__class__.__name__, key)
        return key

    def _build_test_spec_header(self, config, items):
        # first default logical

        # then customized logical
        config.hook.pytest_spec_header(header=self.header,
                                       config=config,
                                       items=items)

    def _build_test_spec_footer(self, config, items):
        # first default logical

        # then customized logical
        config.hook.pytest_spec_footer(footer=self.footer,
                                       config=config,
                                       items=items)

    def _build_test_spec_contents(self, config, items):
        # first default logical
        self._generate_test_spec_content(config, items)
        # then customized logical
        config.hook.pytest_spec_contents(contents=self.contents,
                                         config=config,
                                         items=items)

    def _build_test_spec(self, config, items):
        self._build_test_spec_header(config, items)
        self._build_test_spec_contents(config, items)
        self._build_test_spec_footer(config, items)

    def _generate_test_spec(self, config):
        dir_name = os.path.dirname(self.specfile)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
        with open(self.specfile, 'w') as f:
            for h in self.header:
                f.write(h)
            f.write('\n')
            for content in self.contents:
                f.write(content)
            f.write('\n')
            for t in self.footer:
                f.write(t)

    def pytest_report_collectionfinish(self, config, startdir, items):
        if config.getoption("specpath"):
            self._build_test_spec(config, items)
            self._generate_test_spec(config)

    def pytest_terminal_summary(self, terminalreporter, exitstatus, config):
        terminalreporter.write_sep(
            '-',
            'generated test spec file: {0}'.format(config.option.specpath))

    def pytest_runtestloop(self, session):
        if session.config.option.specpath:
            return True
