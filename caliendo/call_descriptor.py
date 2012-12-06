import cPickle as pickle

from caliendo import config

USE_CALIENDO = config.should_use_caliendo( )
CONFIG       = config.get_database_config( )

if USE_CALIENDO:
    if 'mysql' in CONFIG['ENGINE']:
        from caliendo.db.mysql import *
    else:
        from caliendo.db.sqlite import *

def fetch( hash ):
    """
    Fetches CallDescriptor from the local database given a hash key representing the call. If it doesn't exist returns None.

    :param str hash: The sha1 hexdigest to look the CallDescriptor up by.

    :rtype: CallDescriptor corresponding to the hash passed or None if it wasn't found.
    """
    res = select_io( hash )
    if res:
      p = { 'methodname': '', 'returnval': '', 'args': '' }
      for packet in res:
        hash, methodname, returnval, args, packet_num = packet
        p['methodname'] = p['methodname'] + methodname
        p['returnval']  = p['returnval'] + returnval
        p['args']       = p['args'] + args

      return CallDescriptor( hash, p['methodname'], pickle.loads( str( p['returnval'] ) ), pickle.loads( str( p['args'] ) ) )
    return None


class CallDescriptor:
  """
  This is a basic model representing a function call. It saves the method name,
  a hash key for lookups, the arguments, and return value. This way the call can
  be handled cleanly and referenced later.
  """
  def __init__( self, hash='', method='', returnval='', args='', kwargs='' ):
    """
    CallDescriptor initialiser.

    :param str hash: A hash of the method, order of the call, and arguments.
    :param str method: The name of the method being called.
    :param mixed returnval: The return value of the method. If this isn't pickle-able there will be a problem.
    :param mixed args: The arguments for the method. If these aren't pickle-able there will be a problem.
    """

    self.hash       = hash
    self.methodname = method
    self.returnval  = returnval
    self.args       = args
    self.kwargs     = kwargs

  def __empty_packet(self, packet_num):
    return {
        'hash': '',
        'packet_num': packet_num,
        'methodname': '',
        'args': '',
        'returnval': ''
      }

  def query_buffer(self, methodname, args, returnval):
    class Buf:
      def __init__(self, methodname, args, returnval):
        args                   = pickle.dumps( args )
        returnval              = pickle.dumps( returnval )
        self.__data            = "".join([ methodname, args, returnval ])
        self.__methodname_len  = len( methodname )
        self.__args_len        = len( args )
        self.__returnval_len   = len( returnval )
        self.length            = self.__methodname_len + self.__args_len + self.__returnval_len
        self.char              = 0

      def next(self):
        if self.char + 1 > self.length:
          raise StopIteration

        c         = self.__data[ self.char ]
        attr      = self.attr()
        self.char = self.char + 1

        return c, attr

      def __iter__(self):
        return self

      def attr(self):
        if self.char < self.__methodname_len:
          return 'methodname'
        elif self.char < self.__methodname_len + self.__args_len:
          return 'args'
        else:
          return 'returnval'

    return Buf( methodname, args, returnval )

  def __enumerate_packets(self):
    max_packet_size  = 1024 # 2MB, prolly more like 8MB for 4b char size. MySQL default limit is 16
    buffer           = self.query_buffer( self.methodname, self.args, self.returnval )
    packet_num       = 0
    packets          = [ ]
    while buffer.char < buffer.length:
      p = self.__empty_packet( packet_num )
      packet_length = 0
      for char, attr in buffer:
        p[attr] += char
        packet_length += 1
        if packet_length == max_packet_size:
          break
      packets.append( p )
      packet_num += 1
    return packets

  def enumerate(self):
    self.__enumerate_packets()

  def save( self ):
    """
    Save method for the CallDescriptor.

    If the CallDescriptor matches a past CallDescriptor it updates the existing
    database record corresponding to the hash. If it doesn't already exist it'll
    be INSERT'd.
    """
    packets = self.__enumerate_packets( )
    delete_io( self.hash )
    for packet in packets:
      packet['hash'] = self.hash
      insert_io( packet )

    return self # Supports chaining
