from plugin.core.helpers.variable import merge

from subprocess import Popen
import json
import logging
import os
import subprocess
import sys

CURRENT_PATH = os.path.abspath(__file__)
HOST_PATH = os.path.join(os.path.dirname(CURRENT_PATH), 'host.py')

log = logging.getLogger(__name__)


class BaseTest(object):
    name = None
    optional = False

    @classmethod
    def run(cls, search_paths):
        metadata = {}

        message = None
        success = None

        # Retrieve names of test functions
        names = [
            name for name in dir(cls)
            if name.startswith('test_')
        ]

        if not names:
            return cls.build_failure('No tests defined')

        # Run tests
        for name in names:
            # Ensure function exists
            if not hasattr(cls, name):
                return cls.build_failure('Unable to find function: %r' % name)

            # Run test
            try:
                result = cls.spawn(name, search_paths)

                # Merge test result into `metadata`
                merge(metadata, result, recursive=True)

                # Test successful
                message = None
                success = True
            except Exception, ex:
                if success:
                    continue

                message = ex.message
                success = False

        if not success:
            # Trigger event
            cls.on_failure(message)

            # Build result
            return cls.build_failure(message)

        # Trigger event
        cls.on_success(metadata)

        # Build result
        return cls.build_success(metadata)

    @classmethod
    def spawn(cls, name, search_paths):
        # Find path to python executable
        python_exe = cls.find_python_executable()

        if not python_exe:
            raise Exception('Unable to find python executable')

        # Ensure test host exists
        if not os.path.exists(HOST_PATH):
            raise Exception('Unable to find "host.py" script')

        # Build test process arguments
        args = [
            python_exe, HOST_PATH,
            '--module', cls.__module__,
            '--name', name,

            '--search-paths="%s"' % (
                ';'.join(search_paths)
            ),
        ]

        # Spawn test (in sub-process)
        log.debug('Starting test: %s:%s', cls.__module__, name)

        process = Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for test to complete
        stdout, stderr = process.communicate()

        if stderr:
            log.debug('Test returned messages:\n%s', stderr.replace("\r\n", "\n"))

        # Parse output
        result = None

        if stdout:
            try:
                result = json.loads(stdout)
            except Exception, ex:
                log.warn('Invalid output returned %r - %s', stdout, ex, exc_info=True)

        # Build result
        if process.returncode != 0:
            # Test failed
            if result and 'message' in result:
                raise Exception(result['message'])

            raise Exception('Unknown error (code: %s)' % process.returncode)

        # Test successful
        return result

    @classmethod
    def find_python_executable(cls):
        candidates = [sys.executable]

        # Add candidates relative to the PMS home directory
        pms_home = os.environ.get('PLEX_MEDIA_SERVER_HOME')

        if pms_home and os.path.exists(pms_home):
            candidates.append(os.path.join(pms_home, 'Resources', 'Plex Script Host'))
            candidates.append(os.path.join(pms_home, 'Resources', 'Python', 'bin', 'python'))

        # Use first candidate that exists
        for path in candidates:
            if os.path.exists(path):
                return path

        return None

    #
    # Events
    #

    @classmethod
    def on_failure(cls, message):
        pass

    @classmethod
    def on_success(cls, metadata):
        pass

    #
    # Helpers
    #

    @classmethod
    def build_exception(cls, message, exc_info=None):
        if exc_info is None:
            exc_info = sys.exc_info()

        return cls.build_failure(
            message,
            exc_info=exc_info
        )

    @classmethod
    def build_failure(cls, message, **kwargs):
        result = {
            'success': False,
            'message': message
        }

        # Merge extra attributes
        merge(result, kwargs)

        return result

    @staticmethod
    def build_success(metadata):
        return {
            'success': True,
            'metadata': metadata
        }
