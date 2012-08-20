# -*- coding:utf-8; tab-width:4; mode:python -*-

import inspect

import hamcrest

from .internal import ANY_ARG, create_proxy, InvocationSet, Method, MockBase, get_class
from .matchers import MockExpectInvocation


class Stub(object):
    def __init__(self, collaborator=None):
        self._proxy = create_proxy(collaborator)
        self._stubs = InvocationSet()
        self._recording = False

    def __enter__(self):
        self._recording = True
        return self

    def __exit__(self, *args):
        self._recording = False

    def _manage_invocation(self, invocation):
        self._proxy.assert_signature_matches(invocation)
        if self._recording:
            self._stubs.append(invocation)
            return

        self._do_manage_invocation(invocation)

        if invocation in self._stubs:
            stubbed = self._stubs.lookup(invocation)
            return stubbed.perform(invocation)

        return self._perform_invocation(invocation)

    def _do_manage_invocation(self, invocation):
        pass

    def _perform_invocation(self, invocation):
        return None

    def __getattr__(self, key):
        self._proxy.assert_has_method(key)
        method = Method(self, key)
        setattr(self, key, method)
        return method

    def _classname(self):
        name = self._proxy.collaborator_classname()
        if name is None:
            return self.__class__.__name__
        return name


class Spy(Stub):
    def __init__(self, collaborator=None):
        super(Spy, self).__init__(collaborator)
        self._invocations = InvocationSet()

    def _do_manage_invocation(self, invocation):
        self._invocations.append(invocation)

    def _was_called(self, invocation, times):
        try:
            hamcrest.assert_that(self._invocations.count(invocation),
                                 hamcrest.is_(times))
            return True
        except AssertionError:
            return False

    def _get_invocations_to(self, name):
        return [i for i in self._invocations
                if self._proxy.same_method(name, i.name)]


class ProxySpy(Spy):
    def __init__(self, collaborator):
        assert not inspect.isclass(collaborator), \
            "ProxySpy takes an instance (got %s instead)" % collaborator
        super(ProxySpy, self).__init__(collaborator)

    def _perform_invocation(self, invocation):
        return self._proxy.perform_invocation(invocation)


class Mock(Spy, MockBase):
    def _do_manage_invocation(self, invocation):
        super(Mock, self)._do_manage_invocation(invocation)
        hamcrest.assert_that(self, MockExpectInvocation(invocation))


def Mimic(double, collab):
    def getattribute(self, key):
        if key in ['__class__', '__dict__',
                   '_get_method', '_methods'] or \
                key in [x[0] for x in inspect.getmembers(double)] or \
                key in self.__dict__:
            return object.__getattribute__(self, key)

        return self._get_method(key)

    def _get_method(self, key):
        if key not in self._methods.keys():
            self._proxy.assert_has_method(key)
            method = Method(self, key)
            self._methods[key] = method

        return self._methods[key]

    assert issubclass(double, Stub), \
        "Mimic() takes a double class as first argument (got %s instead)" & double

    collab_class = get_class(collab)
    generated_class = type(
        "Mimic_%s_for_%s" % (double.__name__, collab_class.__name__),
        (double, collab_class) + collab_class.__bases__,
        dict(_methods = {},
             __getattribute__ = getattribute,
             _get_method = _get_method))
    return generated_class(collab)


def method_returning(value):
    with Stub() as stub:
        method = Method(stub, 'unnamed')
        method(ANY_ARG).returns(value)
        return method


def method_raising(exception):
    with Stub() as stub:
        method = Method(stub, 'unnamed')
        method(ANY_ARG).raises(exception)
        return method
