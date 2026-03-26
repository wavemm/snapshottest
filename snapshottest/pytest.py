from __future__ import absolute_import

from termcolor import colored

import pytest
import re

from .module import SnapshotModule, SnapshotTest
from .diff import PrettyDiff
from .reporting import reporting_lines, diff_report


def pytest_addoption(parser):
    group = parser.getgroup('snapshottest')
    group.addoption(
        '--snapshot-update',
        action='store_true',
        default=False,
        dest='snapshot_update',
        help='Update the snapshots while keeping unvisited ones.'
    )
    group.addoption(
        '--snapshot-partial-update',
        action='store_true',
        default=False,
        dest='snapshot_partial_update',
        help='(Deprecated) Alias for --snapshot-update.'
    )
    group.addoption(
        '--snapshot-full-update',
        action='store_true',
        default=False,
        dest='snapshot_full_update',
        help='Update the snapshots and delete unvisited ones.'
    )
    group.addoption(
        '--snapshot-verbose',
        action='store_true',
        default=False,
        help='Dump diagnostic and progress information.'
    )


class PyTestSnapshotTest(SnapshotTest):

    def __init__(self, request=None):
        self.request = request
        super(PyTestSnapshotTest, self).__init__()

    @property
    def module(self):
        return SnapshotModule.get_module_for_testpath(self.request.node.fspath.strpath)

    @property
    def update(self):
        opt = self.request.config.option
        return opt.snapshot_update or opt.snapshot_partial_update or opt.snapshot_full_update

    @property
    def test_name(self):
        cls_name = getattr(self.request.node.cls, '__name__', '')
        flattened_node_name = re.sub(r"\s+", " ", self.request.node.name.replace(r"\n", " "))
        return '{}{} {}'.format(
            '{}.'.format(cls_name) if cls_name else '',
            flattened_node_name,
            self.curr_snapshot
        )


class SnapshotSession(object):
    def __init__(self, config):
        self.verbose = config.getoption("snapshot_verbose")
        self.config = config

    def display(self, tr):
        if not SnapshotModule.has_snapshots():
            return

        tr.write_sep("=", "SnapshotTest summary")

        for line in reporting_lines('pytest'):
            tr.write_line(line)

        opt = tr.config.option
        if opt.snapshot_update or opt.snapshot_partial_update:
            msg = (
                "Snapshots were updated without removing unvisited snapshots. "
                "If you have deleted or renamed tests, old snapshots will be kept. "
                "Run with --snapshot-full-update to remove them."
            )
            print(colored(msg, 'yellow', attrs=['bold']))


def pytest_assertrepr_compare(op, left, right):
    if isinstance(left, PrettyDiff) and op == "==":
        return diff_report(left, right)


@pytest.fixture
def snapshot(request):
    with PyTestSnapshotTest(request) as snapshot_test:
        yield snapshot_test


def pytest_terminal_summary(terminalreporter):
    if terminalreporter.config.option.snapshot_full_update:
        for module in SnapshotModule.get_modules():
            module.delete_unvisited()
            module.save()
    elif terminalreporter.config.option.snapshot_update or terminalreporter.config.option.snapshot_partial_update:
        for module in SnapshotModule.get_modules():
            module.save()

    terminalreporter.config._snapshotsession.display(terminalreporter)

    # Reset loaded snapshots at the end of the test session.
    # Needed for running tests in watch mode.
    SnapshotModule._snapshot_modules = {}


@pytest.mark.trylast  # force the other plugins to initialise, fixes issue with capture not being properly initialised
def pytest_configure(config):
    opt = config.option
    if opt.snapshot_full_update and (opt.snapshot_update or opt.snapshot_partial_update):
        raise pytest.UsageError(
            "--snapshot-full-update cannot be combined with "
            "--snapshot-update or --snapshot-partial-update"
        )
    config._snapshotsession = SnapshotSession(config)
    # config.pluginmanager.register(bs, "snapshottest")
