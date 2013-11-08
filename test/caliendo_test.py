import inspect
import tempfile
import weakref
import unittest
import hashlib
import pickle
import sys
import os

os.environ['USE_CALIENDO'] = 'True'

from caliendo.db.flatfiles import CACHE_DIRECTORY 
from caliendo.db.flatfiles import SEED_DIRECTORY 
from caliendo.db.flatfiles import EV_DIRECTORY 
from caliendo.db.flatfiles import LOG_FILEPATH 
from caliendo.db.flatfiles import read_used
from caliendo.db.flatfiles import read_all
from caliendo.db.flatfiles import delete_from_directory_by_hashes
from caliendo.db.flatfiles import purge
from caliendo.call_descriptor import CallDescriptor
from caliendo.call_descriptor import fetch
from caliendo.facade import patch
from caliendo.facade import Facade
from caliendo.facade import Wrapper
from caliendo.facade import cache
from caliendo.util import is_primitive
from caliendo.util import recache
from caliendo.util import serialize_args
from caliendo import util
from caliendo import expected_value
from caliendo import config
import caliendo

from nested.bazbiz import baz
from foobar import bazbiz
from api import foobarfoobiz
from api import foobarfoobaz
from api import foobar
from api import foobiz
from api import foobaz
from test.api.services.bar import find as find_bar
from test.api.myclass import MyClass

recache()

class TestModel:
    def __init__(self, a, b):
        setattr( self, 'a', a )
        setattr( self, 'b', b )

class CallOnceEver:
    __die = 0
    def update(self):
        if self.__die:
            raise Exception("NOPE!")
        else:
            self.__die = 1
            return 1

class CallsServiceInInit:
    __die = 0
    def __init__(self):
        if self.__die:
            raise Exception("NOPE!")
        else:
            self.__die = 1

    def methoda(self):
        return 'a'

    def nested_init(self):
        return CallsServiceInInit()


class TestA:
    def getb(self):
        return TestB()

class TestB:
    def getc(self):
        return TestC()

class TestC:
    __private_var   = 0
    lambda_function = lambda s, x: x * 2
    test_a_class    = TestA
    some_model      = TestModel( a=1, b=2 )
    primitive_a     = 'a'
    primitive_b     = 1
    primitive_c     = [ 1 ]
    primitive_d     = { 'a': 1 }

    def methoda(self):
        return "a"
    def methodb(self):
        return "b"
    def update(self):
        return "c"
    def increment(self):
        self.__private_var = self.__private_var + 1
        return self.__private_var

class LazyBones(dict):
    def __init__(self):
        self.store = {}

    def __getattr__(self, attr):
        if attr == 'c':
            return lambda : TestC()
        else:
            self.store[attr] = None
            return self.store[attr]

class  CaliendoTestCase(unittest.TestCase):
    def setUp(self):
        caliendo.util.register_suite()

    def test_call_descriptor(self):
        hash      = hashlib.sha1( "adsf" ).hexdigest()
        method    = "mymethod"
        returnval = {'thisis': [ 'my', 'return','val' ] }
        args      = ( 'a', 'b', 'c' )
        #self, hash='', stack='', method='', returnval='', args='', kwargs='' ):
        cd = CallDescriptor(
            hash=hash,
            stack='',
            method=method,
            returnval=returnval,
            args=args )

        cd.save() 

        self.assertEqual( cd.hash, hash )
        self.assertEqual( cd.methodname, method )
        self.assertEqual( cd.returnval, returnval )
        self.assertEqual( cd.args, args )

        cd = fetch( hash )

        self.assertEqual( cd.hash, hash )
        self.assertEqual( cd.methodname, method )
        self.assertEqual( cd.returnval, returnval )
        self.assertEqual( cd.args, args )

    def test_serialize_basics(self):
        basic_list = [ 'a', 'b', 'c' ]
        basic_dict = { 'a': 1, 'b': 2, 'c': 3 }
        nested_list = [ [ 0, 1, 2 ], [ 3, 4, 5 ] ]
        nested_dict = { 'a': { 'a': 1, 'b': 2 }, 'b': { 'c': 3, 'd': 4 } }
        list_of_nested_dicts = [ { 'a': { 'a': 1, 'b': 2 }, 'b': { 'c': 3, 'd': 4 } } ]

        s_basic_list = serialize_args(basic_list)
        s_basic_dict = serialize_args(basic_dict)
        s_nested_list = serialize_args(nested_list)
        s_nested_dict = serialize_args(nested_dict)
        s_list_of_nested_dicts = serialize_args(list_of_nested_dicts)

        assert s_basic_list == str(['a', 'b', 'c'])
        assert s_basic_dict == str(["['1', 'a']", "['2', 'b']", "['3', 'c']"])
        assert s_nested_list == str(["['0', '1', '2']", "['3', '4', '5']"])
        assert s_nested_dict == str(['[\'["[\\\'1\\\', \\\'a\\\']", "[\\\'2\\\', \\\'b\\\']"]\', \'a\']', '[\'["[\\\'3\\\', \\\'c\\\']", "[\\\'4\\\', \\\'d\\\']"]\', \'b\']'])
        assert s_list_of_nested_dicts == str(['[\'[\\\'["[\\\\\\\'1\\\\\\\', \\\\\\\'a\\\\\\\']", "[\\\\\\\'2\\\\\\\', \\\\\\\'b\\\\\\\']"]\\\', \\\'a\\\']\', \'[\\\'["[\\\\\\\'3\\\\\\\', \\\\\\\'c\\\\\\\']", "[\\\\\\\'4\\\\\\\', \\\\\\\'d\\\\\\\']"]\\\', \\\'b\\\']\']'])

    def test_serialize_iterables(self):
        target_set = set([5, 3, 4, 2, 7, 6, 1, 8, 9, 0])
        def gen():
            for i in range(10):
                yield i
        target_generator = gen()
        target_frozenset = frozenset([5, 3, 4, 2, 7, 6, 1, 8, 9, 0])

        s_set = serialize_args(target_set)
        s_gen = serialize_args(target_generator)
        s_frozenset = serialize_args(target_frozenset)

        assert s_set == s_gen
        assert s_gen == s_frozenset
        assert s_frozenset == str(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'])


    def test_serialize_nested_lists(self):
        a = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        b = [[7, 8, 9], [4, 5, 6], [1, 2, 3]]
        c = [[6, 4, 5], [1, 3, 2], [9, 8, 7]]

        s_a = serialize_args(a)
        s_b = serialize_args(b)
        s_c = serialize_args(c)

        assert s_a == s_b
        assert s_b == s_c
        assert s_c == str(["['1', '2', '3']", "['4', '5', '6']", "['7', '8', '9']"])

    def test_serialize_nested_lists_of_nested_lists(self):
        a = [[[1, 2, 3], [4, 5, 6]], [7, 8, 9]]
        b = [[7, 8, 9], [[4, 5, 6], [1, 2, 3]]]
        c = [[[6, 4, 5], [1, 3, 2]], [9, 8, 7]]

        s_a = serialize_args(a)
        s_b = serialize_args(b)
        s_c = serialize_args(c)

        assert s_a == s_b
        assert s_b == s_c
        assert s_c == str(['["[\'1\', \'2\', \'3\']", "[\'4\', \'5\', \'6\']"]', "['7', '8', '9']"])

    def test_serialize_dicts(self):
        a = {'a': 1, 'b': 2, 'c': 3}
        b = {'c': 3, 'a': 1, 'b': 2}
        c = {'c': 3, 'b': 2, 'a': 1}
        d = {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6, 'g': 7, 'h': 8}
        e = {'b': 2, 'a': 1, 'h': 8, 'd': 4, 'e': 5, 'f': 6, 'g': 7, 'c': 3}
        f = {'e': 5, 'a': 1, 'h': 8, 'd': 4, 'b': 2, 'f': 6, 'g': 7, 'c': 3}

        s_a = serialize_args(a)
        s_b = serialize_args(b)
        s_c = serialize_args(c)
        s_d = serialize_args(d)
        s_e = serialize_args(e)
        s_f = serialize_args(f)

        assert s_a == s_b
        assert s_b == s_c
        assert s_c == str(["['1', 'a']", "['2', 'b']", "['3', 'c']"])

        assert s_d == s_e
        assert s_e == s_f
        assert s_f == str(["['1', 'a']", "['2', 'b']", "['3', 'c']", "['4', 'd']", "['5', 'e']", "['6', 'f']", "['7', 'g']", "['8', 'h']"])

    def test_serialize_models(self):
        a = TestModel('a', 'b')
        b = [TestModel('a', 'b'), TestModel('b', 'c'), TestModel('c', 'd')]
        c = {'c': TestModel('a', 'b'), 'b': TestModel('b', 'c'), 'a': TestModel('c', 'd')}
        d = set([TestModel('a', 'b'), TestModel('b', 'c'), TestModel('c', 'd')])

        s_a = serialize_args(a)
        s_b = serialize_args(b)
        s_c = serialize_args(c)
        s_d = serialize_args(d)

        assert s_a == 'TestModel'
        assert s_b == str(['TestModel', 'TestModel', 'TestModel'])
        assert s_c == str(["['TestModel', 'a']", "['TestModel', 'b']", "['TestModel', 'c']"])
        assert s_d == str(['TestModel', 'TestModel', 'TestModel'])

    def test_serialize_methods(self):
        a = lambda *args, **kwargs: 'foo'
        def b():
            return 'bar'
        class C:
            def c(self):
                return 'biz'

        serialize_args(a) == '<lambda>'
        serialize_args(b) == 'b'
        serialize_args(C().c) == 'c'

    def test_fetch_call_descriptor(self):
        hash      = hashlib.sha1( "test1" ).hexdigest()
        method    = "test1"
        returnval = { }
        args      = ( )

        cd = CallDescriptor( hash=hash, stack='', method=method, returnval=returnval, args=args )
        cd.save( )

        cd = fetch( hash )
        self.assertEquals( cd.hash, hash )
        self.assertEquals( cd.methodname, method )

        hash      = hashlib.sha1( "test1" ).hexdigest()
        method    = "test2"
        cd.methodname = method
        cd.save( )

        cd = fetch( hash )
        self.assertEquals( cd.hash, hash )
        self.assertEquals( cd.methodname, method )

        hash      = hashlib.sha1( "test3" ).hexdigest()
        method    = "test3"
        cd.hash   = hash
        cd.methodname = method
        cd.save( )

        cd = fetch( hash )
        self.assertEquals( cd.hash, hash )
        self.assertEquals( cd.methodname, method )

    def test_facade(self):
        mtc = TestC( )
        mtc_f = Facade( mtc )

        self.assertEquals( mtc.methoda( ), mtc_f.methoda( ) )
        self.assertEquals( mtc.methodb( ), mtc_f.methodb( ) )
        self.assertEquals( mtc_f.methoda( ), "a" )

        self.assertEquals( mtc_f.increment( ), 1 ) 
        self.assertEquals( mtc_f.increment( ), 2 ) 
        self.assertEquals( mtc_f.increment( ), 3 ) 
        self.assertEquals( mtc_f.increment( ), 4 ) 

    def test_update(self):
        o = CallOnceEver()
        test = self


        def test(fh):
            op = Facade( o )
            result = o.update()
            fh.write(str(result == 1))
            fh.close()
            os._exit(0)

        outputs = [ tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False) ]

        for output in outputs:
            pid = os.fork()
            if pid:
                os.waitpid(pid, 0)
            else:
                test(output)

        expected = ['True', 'True', 'True']
        result   = []

        for output in outputs:
            output.close()

            fh = open(output.name)
            result.append(fh.read())
            fh.close()

            os.remove(output.name)

        self.assertEqual(result, expected)

    def test_recache(self):
        mtc = TestC( )
        mtc_f = Facade( mtc )

        hashes = []

        self.assertEquals( mtc.methoda( ), mtc_f.methoda( ) )
        self.assertIsNotNone(mtc_f.last_cached)
        hashes.append( mtc_f.last_cached )
        self.assertEquals( mtc.methodb( ), mtc_f.methodb( ) )
        self.assertIsNotNone(mtc_f.last_cached)
        hashes.append( mtc_f.last_cached )
        self.assertEquals( mtc_f.methoda( ), "a" )
        self.assertIsNotNone(mtc_f.last_cached)
        hashes.append( mtc_f.last_cached )

        self.assertEquals( mtc_f.increment( ), 1 )
        self.assertIsNotNone(mtc_f.last_cached)
        hashes.append( mtc_f.last_cached )
        self.assertEquals( mtc_f.increment( ), 2 ) 
        self.assertIsNotNone(mtc_f.last_cached)
        hashes.append( mtc_f.last_cached )
        self.assertEquals( mtc_f.increment( ), 3 ) 
        self.assertIsNotNone(mtc_f.last_cached)
        hashes.append( mtc_f.last_cached )
        self.assertEquals( mtc_f.increment( ), 4 )
        self.assertIsNotNone(mtc_f.last_cached)
        hashes.append( mtc_f.last_cached )

        # Ensure hashes are now in db:
        for hash in hashes:
            self.assertIsNotNone(hash, "Hash is none. whoops.")
            cd = fetch( hash )
            self.assertTrue( cd is not None, "%s was not found" % hash )
            self.assertEquals( cd.hash, hash, "%s was not found" % hash )

        # Delete some:
        caliendo.util.recache( 'methodb', 'caliendo_test.py' )
        caliendo.util.recache( 'methoda', 'caliendo_test.py' )

        # Ensure they're gone:
        methodb = hashes[0]
        methoda = hashes[1]
        cd = fetch( methodb )

        self.assertIsNone( cd, "Method b failed to recache." )
        cd = fetch( methoda )

        self.assertIsNone( cd, "Method a failed to recache." )

        # Ensure the rest are there:
        hashes = hashes[3:]
        for hash in hashes:
            cd = fetch( hash )
            self.assertEquals( cd.hash, hash )

        # Delete them ALL:
        caliendo.util.recache()

        #Ensure they're all gone:
        for hash in hashes:
            cd = fetch( hash )
            self.assertIsNone( cd )

    def test_chaining(self):
        a = TestA()
        b = a.getb()
        c = b.getc()

        self.assertEquals( a.__class__, TestA )
        self.assertEquals( b.__class__, TestB )
        self.assertEquals( c.__class__, TestC )

        a_f = Facade(TestA())
        b_f = a_f.getb()
        c_f = b_f.getc()

        self.assertEquals( a_f.__class__, Facade(a).__class__ )
        self.assertEquals( b_f.__class__, Facade(a).__class__ )
        self.assertEquals( c_f.__class__, Facade(a).__class__ )

        self.assertEquals( 'a', c_f.methoda() )

    def test_various_attribute_types(self):
        c = Facade(TestC())

        # 'Primitives'
        self.assertEquals( c.primitive_a, 'a' )
        self.assertEquals( c.primitive_b, 1 )
        self.assertEquals( c.primitive_c, [ 1 ] )
        self.assertEquals( c.primitive_d, { 'a': 1 } )

        # Instance methods
        self.assertEquals( c.methoda(), 'a' )
        self.assertEquals( c.methodb(), 'b' )

        # Lambda functions
        self.assertEquals( c.lambda_function( 2 ), 4 )

        # Models
        self.assertEquals( c.some_model.a, 1 )
        self.assertEquals( c.some_model.b, 2 )

        # Classes
        self.assertEquals( c.test_a_class( ).wrapper__unwrap( ).__class__, TestA )

    def test_various_attribute_types_after_chaining(self):
        c = Facade(TestA()).getb().getc()

        # 'Primitives'
        self.assertEquals( c.primitive_a, 'a' )
        self.assertEquals( c.primitive_b, 1 )
        self.assertEquals( c.primitive_c, [ 1 ] )
        self.assertEquals( c.primitive_d, { 'a': 1 } )

        # Instance methods
        self.assertEquals( c.methoda(), 'a' )
        self.assertEquals( c.methodb(), 'b' )

        # Lambda functions
        self.assertEquals( c.lambda_function( 2 ), 4 )

        # Models
        self.assertEquals( c.some_model.a, 1 )
        self.assertEquals( c.some_model.b, 2 )

        # Classes
        self.assertEquals( c.test_a_class( ).wrapper__unwrap( ).__class__, TestA )

    def test_model_interface(self):
        a = Facade(TestA())

        a.attribute_a = "a"
        a.attribute_b = "b"
        a.attribute_c = "c"

        self.assertEquals( a.attribute_a, "a")
        self.assertEquals( a.attribute_b, "b")
        self.assertEquals( a.attribute_c, "c")

    def test_exclusion_list(self):
        # Ignore an instance:
        a = Facade(TestA())

        b = a.getb()
        self.assertEquals( b.__class__, Wrapper )

        a.wrapper__ignore( TestB )
        b = a.getb()
        self.assertEquals( b.__class__, TestB )

        a.wrapper__unignore( TestB )
        b = a.getb()
        self.assertEquals( b.__class__, Wrapper )
        
        # Ignore a class:
        c = Facade(TestC())

        self.assertTrue( c.test_a_class().__class__, Wrapper )

        c.wrapper__ignore( TestA )
        a = c.test_a_class()
        self.assertTrue( isinstance( a, TestA ) )

    def test_lazy_load(self):
        # Write class where a method is defined using __getattr__
        lazy = Facade(LazyBones())
        c = lazy.c()
        self.assertEquals( c.__class__, Wrapper )
        self.assertEquals( c.wrapper__unwrap().__class__, TestC )
        self.assertEquals( c.methoda(), 'a' )

    def test_service_call_in__init__(self):
        test = self

        def test(fh):
            o = Facade( cls=CallsServiceInInit )
            result = o.methoda()
            fh.write(str(result == 'a'))
            fh.close()
            os._exit(0)

        outputs = [ tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False) ]

        for output in outputs:
            pid = os.fork()
            if pid:
                os.waitpid(pid, 0)
            else:
                test(output)

        expected = ['True', 'True', 'True']
        result   = []

        for output in outputs:
            output.close()

            fh = open(output.name)
            result.append(fh.read())
            fh.close()

            os.remove(output.name)

        self.assertEqual(result, expected)

    def test_service_call_in_nested__init__(self):
        test = self

        def test(fh):
            o = Facade( cls=CallsServiceInInit )
            result = o.nested_init().methoda()
            fh.write(str(result == 'a'))
            fh.close()
            os._exit(0)

        outputs = [ tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False) ]

        for output in outputs:
            pid = os.fork()
            if pid:
                os.waitpid(pid, 0)
            else:
                test(output)

        expected = ['True', 'True', 'True']
        result   = []

        for output in outputs:
            output.close()

            fh = open(output.name)
            result.append(fh.read())
            fh.close()

            os.remove(output.name)

        self.assertEqual(result, expected)

    def test_mock_weak_ref(self):
        import pickle
        import weakref

        class A:
            def methoda(self):
                return 'a'

        a = A()
        b = A()
        c = A()

        a.b = b
        a.ref_b = weakref.ref(b)
        a.ref_c = weakref.ref(c)

        test = self

        def test(fh):
            o = Facade( a )
            result = o.methoda()
            fh.write(str(result == 'a'))
            fh.close()
            os._exit(0)

        outputs = [ tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False) ]

        for output in outputs:
            pid = os.fork()
            if pid:
                os.waitpid(pid, 0)
            else:
                test(output)

        expected = ['True', 'True', 'True']
        result   = []

        for output in outputs:
            output.close()

            fh = open(output.name)
            result.append(fh.read())
            fh.close()

            os.remove(output.name)

        self.assertEqual(result, expected)

    def test_truncation(self):
        from caliendo import pickling
        pickling.MAX_DEPTH = 2
        cls = TestA()
        a = {
          'a': {
            'b': {
              'c': [{
                'd': {
                  'e': {
                    'f': {
                      'a': weakref.ref(cls),
                      'b': 2,
                      'c': 3
                    }
                  }
                }
              },{
                'd': {
                  'e': {
                    'f': {
                      'a': 1,
                      'b': 2,
                      'c': 3
                    }
                  }
                }
              }]
            }
          },
          'b': {
            'a': 1,
            'b': 2
          }
        }
        b = pickle.loads(pickling.pickle_with_weak_refs(a))
        self.assertEquals( b, {'a': {'b': {'c': [{}, {}]}}, 'b': {'a': 1, 'b': 2}} )

    def test_cache_positional(self):

        def positional(x, y, z):
            CallOnceEver().update()
            return x + y + z

        def test(fh):
            result = cache( positional, args=(1,2,3) )
            fh.write(str(result == 6))
            fh.close()
            os._exit(0)

        outputs = [ tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False) ]

        for output in outputs:
            pid = os.fork()
            if pid:
                os.waitpid(pid, 0)
            else:
                test(output)

        expected = ['True', 'True', 'True']
        result   = []

        for output in outputs:
            output.close()

            fh = open(output.name)
            result.append(fh.read())
            fh.close()

            os.remove(output.name)

        self.assertEqual(result, expected)

    def test_cache_keyword(self):
        def keyword(x=1, y=1, z=1):
            CallOnceEver().update()
            return x + y + z

        def test(fh):
            result = cache( keyword, kwargs={ 'x': 1, 'y': 2, 'z': 3 } )
            fh.write(str(result == 6))
            fh.close()
            os._exit(0)

        outputs = [ tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False) ]

        for output in outputs:
            pid = os.fork()
            if pid:
                os.waitpid(pid, 0)
            else:
                test(output)

        expected = ['True', 'True', 'True']
        result   = []

        for output in outputs:
            output.close()

            fh = open(output.name)
            result.append(fh.read())
            fh.close()

            os.remove(output.name)

        self.assertEqual(result, expected)

    def test_cache_mixed(self):
        def mixed(x, y, z=1):
            CallOnceEver().update()
            return x + y + z

        def test(fh):
            result = cache( mixed, args=(1,2), kwargs={'z': 3 } )
            fh.write(str(result == 6))
            fh.close()
            os._exit(0)

        outputs = [ tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False) ]

        for output in outputs:
            pid = os.fork()
            if pid:
                os.waitpid(pid, 0)
            else:
                test(output)

        expected = ['True', 'True', 'True']
        result   = []

        for output in outputs:
            output.close()

            fh = open(output.name)
            result.append(fh.read())
            fh.close()

            os.remove(output.name)

        self.assertEqual(result, expected)


    @patch('test.nested.bazbiz.baz', 'biz')
    def test_patch_sanity(self):
        b = baz()
        assert b == 'biz', "Value is %s" % b

    @patch('test.nested.bazbiz.baz', 'boz')
    def test_patch_context_a(self):
        b = baz()
        assert b == 'boz', "Expected boz got %s" % b


    @patch('test.nested.bazbiz.baz', 'bar')
    def test_patch_context_b(self):
        b = baz()
        assert b == 'bar', "Expected bar got %s" % b

    @patch('test.nested.bazbiz.baz', 'biz')
    def test_patch_depth(self):
        b = bazbiz()
        assert b == 'bizbiz', "Expected bizbiz, got %s" % bazbiz()

    @patch('test.nested.bazbiz.baz')
    def test_patched_cache(self):
        def mixed(x, y, z=1):
            CallOnceEver().update()
            return x + y + z

        def test(fh):
            result = baz() 
            fh.write(str(result == 'baz'))
            fh.close()
            os._exit(0)

        outputs = [ tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False),
                    tempfile.NamedTemporaryFile(delete=False) ]

        for output in outputs:
            pid = os.fork()
            if pid:
                os.waitpid(pid, 0)
            else:
                test(output)

        expected = ['True', 'True', 'True']
        result   = []

        for output in outputs:
            output.close()

            fh = open(output.name)
            result.append(fh.read())
            fh.close()

            os.remove(output.name)

        self.assertEqual(result, expected)


    def test_expected_value_prompt(self):
        assert expected_value.is_equal_to(2)

    def test_multiple_expected_value_calls(self):
        assert expected_value.is_equal_to(2)
        assert expected_value.is_equal_to(3)
        assert expected_value.is_equal_to(4)


    @patch('test.api.services.bar.find')
    @patch('test.api.services.baz.find')
    @patch('test.api.services.biz.find')
    @patch('test.api.services.foo.find')
    def test_multiple_overlapping_services_a(self):
        foobarfoobizzes = foobarfoobiz.find(10)

    @patch('test.api.services.bar.find')
    @patch('test.api.services.baz.find')
    @patch('test.api.services.biz.find')
    @patch('test.api.services.foo.find')
    def test_multiple_overlapping_services_b(self):
        foobarfoobazzes = foobarfoobaz.find(10)
        foobarfoobizzes = foobarfoobiz.find(10)
        foobars = foobar.find(10)
        foobarfoobazzes = foobarfoobaz.find(10)

    @patch('test.api.services.bar.find')
    @patch('test.api.services.baz.find')
    @patch('test.api.services.biz.find')
    @patch('test.api.services.foo.find')
    def test_multiple_overlapping_services_c(self):
        foobizs = foobiz.find(10)
        foobars = foobar.find(10)

    @patch('test.api.services.bar.find', side_effect=Exception("Blam"))
    def test_side_effect_raises_exceptions(self):
        try:
            foobizs = foobiz.find(10)
            foobars = foobar.find(10)
        except:
            assert sys.exc_info()[1].message == 'Blam'

    @patch('test.api.services.bar.find', rvalue='la', side_effect=Exception('Boom'))
    def test_side_effect_raises_exceptions_with_rvalue(self):
        try:
            find_bar(10)
        except:
            assert sys.exc_info()[1].message == 'Boom'

    @patch('test.api.services.bar.find', rvalue='la', side_effect=lambda a: a)
    def test_side_effect_overrides_rvalue(self):
        rvalue = find_bar(10)
        assert rvalue == 10, "Expected la, got %s" % rvalue

    @patch('test.api.myclass.MyClass.foo', rvalue='bar')
    def test_patching_bound_methods(self):
        mc = MyClass()
        bar = mc.foo()
        assert bar == 'bar', "Got '%s' expected 'bar'" % bar

    @patch('test.api.services.bar.find')
    @patch('test.api.services.baz.find')
    @patch('test.api.services.biz.find')
    @patch('test.api.services.foo.find')
    def test_purge(self):
      from api.services.foo import find as find_foo
      from api.services.biz import find as find_biz
      from api.services.baz import find as find_baz
      from api.services.bar import find as find_bar
      
      delete_from_directory_by_hashes(CACHE_DIRECTORY, '*')
      delete_from_directory_by_hashes(EV_DIRECTORY, '*')
      delete_from_directory_by_hashes(SEED_DIRECTORY, '*')

      all_hashes = read_all()
      assert len(all_hashes['evs']) == 0
      assert len(all_hashes['cache']) == 0
      assert len(all_hashes['seeds']) == 0

      with open(LOG_FILEPATH, 'w+') as fp:
          pass

      expected_value.is_equal_to(find_foo(1))
      expected_value.is_equal_to(find_biz(1))
      expected_value.is_equal_to(find_baz(1))
      expected_value.is_equal_to(find_bar(1))

      spam = read_all()
      assert len(spam['evs']) != 0
      assert len(spam['cache']) != 0
      assert len(spam['seeds']) != 0
      
      with open(LOG_FILEPATH, 'w+') as fp:
          pass

      expected_value.is_equal_to(find_foo(1))
      expected_value.is_equal_to(find_biz(1))
      expected_value.is_equal_to(find_baz(1))
      expected_value.is_equal_to(find_bar(1))

      spam_and_ham = read_all() 
      purge() 
      ham = read_all()

      for kind, hashes in ham.items():
          for h in hashes:
              assert h not in spam[kind]

      for kind, hashes in spam.items():
          for h in hashes:
              assert h not in ham[kind]

      for kind, hashes in spam_and_ham.items():
          for h in hashes:
              assert h in spam[kind] or h in ham[kind]

if __name__ == '__main__':
    unittest.main()


