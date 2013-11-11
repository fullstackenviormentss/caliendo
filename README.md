# About

Caliendo is a very simple interface for mocking APIs. It allows you to skip
(potentially heavy) calls to your database or remote resources by storing sets
of calls and caching responses based on the sequence of execution as well as
function arguments. In some cases this improves unit test performance by
several orders of magnitude.

# Installation

Caliendo is set up to install with `pip`. You can install it directly from
GitHub by running:

```console
pip install git+git://github.com/buzzfeed/caliendo.git#egg=caliendo
```

Alternatively if you have a copy of the source on your machine; cd to the
parent directory and run:

```console
pip install ./caliendo
```

To run tests you can use the standard unittest module. You'll have various 
prompts during the process. You can just hit ctrl+d to continue. To run all 
tests you should use nose with --nocapture. nose capturing interferes with 
the interactive prompts.

Your tests will need to be written is TestCases of some sort (classes). 
Caliendo uses the TestCase instance to figure out what module the test came 
from at runtime by referring to self, which is the first argument to the 
test methods. 

```console

python setup.py test 
```

```console

nosetests --all-modules --nocapture test/
```

# Configuration

Caliendo requires file read/write permissions for caching objects. The first time
you invoke tests calling caliendo:

1. Caliendo writes to the specified cache files. The default location is in the 
   caliendo build, caliendo/cache, caliendo/evs, and caliendo/seeds, and 
   caliendo/used. You can change where caliendo creates these directories and 
   file by setting the environment variable:

```console
export CALIENDO_CACHE_PREFIX=/some/absolute/path

```

2. If you would like to be prompted to overwrite or modify existing cached values
   you can write the environment variable CALIENDO_PROMPT.

```console
export CALIENDO_PROMPT=True

```

# Examples

Here are a few basic examples of use.

## The cache.

Caliendo offers a cache which decorates callables. If you pass the cache the handle for the callable, and the args/kwargs; it will be 'cached'. The behavior is a little complex. Explained below:
  *When the method is called the first time a counter is issued that is keyed on a hash of the stack trace and a serialization of the function parameters. 
  *If/When a matching hash is generated (e.g. a method is called with the same parameters by the same calling method the counter is incremented. 
  *With each unique counter the result of the function call is pickled and stored matching a CallDescriptor. If a return value can't be pickled caliendo will attempt to munge it. If caliendo fails to munge it an error will be thrown. 
  *When a method is called that matches an existing counter; the stored CallDescriptor rebuilds the original call and the original return value is returned by the cache. 

```python
from caliendo.facade import cache

global side_effect
side_effect = 0
def foo():
  global side_effect
  side_effect += 1
  return side_effect

for i in range(3):
  assert cache(handle=foo) == i + 1

print side_effect
```

When the above example is run the first time; it will print 2. For every subsequent time it is run it will print 0 unless caliendo's cache is cleared.

## Service patching. 

An interface inspired greatly by python Mock is `patch()`.

`patch()` is intended to be used as a decorator for integration/unit tests that need to be decoupled from external services.

When `patch` is called it returns the test it decorates in the context of the specified method replaced by it's `caliendo.facade.cache` decorated version.

When the decorated test is invoked it is patched at runtime. After the test returns it is automatically unpatched.

`patch`, by default, uses `caliendo.facade.cache`. If you pass an `rvalue` as the second parameter; your patched method will return that value.

```python

# Pretend these methods are all defined in various modules in the codebase.
# Let foo() be defined in api.services.foos
def foo():
  return 'foo'
# Let bar() be defined in api.services.bars
def bar():
  return foo()
# Let baz be defined in api.bazs
def baz():
  return bar()

# Now for our test suite.
import unittest
from caliendo.patch import patch
from api.bazs import baz

class ApiTest(unittest.TestCase):

  @patch('api.services.bars.bar', rvalue='biz')
  def test_baz(self):
    assert baz() == 'biz'
```

In the above example `bar` is nested in the service layer of the architecture. We can import it once at the head of the test suite and effectively patch it at the test's invocation. 

We set the rvalue to 'biz', but if we left it alone the value 'foo' would have been cached on the initial run. Every subsequent run would not have called the `foo` or `bar` method, and would have simply returned the cached value from the initial invokation of the test. 

## Purge

You can purge unused cache file from the cache by using the purge functionality at `caliendo.db.flatfiles.purge`.

By including a call to purge at the end of a full run of the tests; any unused portion of any part of the cache will be erased.

This is a good way to commit minimal files to your code base.

```python

from caliendo.db.flatfiles import purge

# Run all your tests:
unittest.main()

# Then purge unused files.
purge()

```

## The Facade 

This is the buggiest feature of `caliendo`. 

If you have an api you want to run under Caliendo you can invoke it like so:

```python
some_api     = SomeAPI()
caliendo_api = Facade( some_api ) # Note: caliendo is invoked with the INSTANCE, not the CLASS
```

## Chaining

As of revision v0.0.19 caliendo supports chaining so you can invoke it like:

```python
caliendo_api = Facade(some_api)
baz = caliendo_api.get_foo().get_bar().get_baz() 
```

If type(baz) is not in ( float, long, str, int, dict, list, unicode ) it will be automatically wrapped by caliendo. 

## Type Checking

Some APIs check the types or __class__ of the variables being passed in. A caliendo facade will have a class, `caliendo.facade.Wrapper`.

In order to unwrap an object to be type-checked by the target API you have to invoke the `wrapper__unwrap()` method on the Facade'd API releasing the object to the target API.

A second method allows the implementer to specify a list of object to avoid Facading entirely. (Useful for exporting models).

```python
facaded_api = Facade(SOMEAPI())
facaded_api.wrapper__ignore( somemodule.SomeClassDefinition )
```

The above example will ensure objects with `__class__` `somemodule.SomeClassDefinition` will never be wrapped. 

To stop ignoring a particular class you can do:

```python
facaded_api = Facade(SOMEAPI())
facaded_api.wrapper__ignore( somemodule.SomeClassDefinition )
facaded_api.wrapper__unignore( somemodule.SomeClassDefinition )
```

# Execution

Once you have an instance of an API running under a `Facade` you should be able
to call all the methods normally.

# Troubleshooting

1. If you start getting unexpected API results you should clear the cache by
   simply deleting all the rows in the `test_io` table.

2. Caliendo doesn't support a large level of nested objects in arguments or
   return values. If you start getting unexpected results this may be the
   problem. Better nesting is to come.

3. If you alternate between calls to the `Facade` instance of an API and the
   API itself you will probably see unexpected results. Caliendo maintains
   the state of the API by maintaining a reference to the API internally.

4. If you have a class inheriting from `dict` you'll need to define a
   `__getstate__` and a `__setstate__` method. Described:
   [http://stackoverflow.com/questions/5247250/why-does-pickle-getstate-accept-as-a-return-value-the-very-instance-it-requi]

5. If you're trying to mock a module that contains class definitions; you can
   use the classes normally except that the type will be that of a lambda
   function instead of a class.
