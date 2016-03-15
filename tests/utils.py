import pytest


def fail_test(loop, context):  # pragma: no cover
    loop.test_failure = context


def setup_test_loop(loop):
    loop.set_exception_handler(fail_test)
    loop.test_failure = None


def check_loop_failures(loop):  # pragma: no cover
    if loop.test_failure is not None:
        pytest.fail('{message}: {exception}'.format(**loop.test_failure))


@pytest.fixture
def glib_policy():
    from gbulb.glib_events import GLibEventLoopPolicy
    return GLibEventLoopPolicy()


@pytest.fixture
def gtk_policy():
    from gbulb.gtk import GtkEventLoopPolicy
    return GtkEventLoopPolicy()


@pytest.yield_fixture(scope='function')
def glib_loop():
    l = glib_policy().new_event_loop()
    setup_test_loop(l)
    yield l
    check_loop_failures(l)
    l.close()


@pytest.yield_fixture(scope='function')
def gtk_loop():
    l = gtk_policy().new_event_loop()
    setup_test_loop(l)
    yield l
    check_loop_failures(l)
    l.close()
