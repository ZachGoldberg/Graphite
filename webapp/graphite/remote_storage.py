import socket
import time
import httplib
from urllib import urlencode
try:
  import cPickle as pickle
except ImportError:
  import pickle


class RemoteStore(object):
  timeout = 5
  lastFailure = 0.0
  retryDelay = 10
  available = property(lambda self: time.time() - self.lastFailure > self.retryDelay)

  def __init__(self, host):
    self.host = host

  def find(self, query):
    request = FindRequest(self, query)
    request.send()
    return request

  def fail(self):
    self.lastFailure = time.time()


class FindRequest:
  suppressErrors = True

  def __init__(self, store, query):
    self.store = store
    self.query = query
    self.connection = None

  def send(self):
    self.connection = HTTPConnectionWithTimeout(self.store.host)
    self.connection.timeout = self.store.timeout
    try:
      self.connection.request('GET', '/metrics/find/?local=1&format=pickle&query=' + self.query)
    except:
      self.store.fail()
      if not self.suppressErrors:
        raise

  def get_results(self):
    if not self.connection:
      self.send()

    try:
      response = self.connection.getresponse()
      assert response.status == 200, "received error response %s - %s" % (response.status, response.reason)
      result_data = response.read()
      results = pickle.loads(result_data)
    except:
      self.store.fail()
      if not self.suppressErrors:
        raise
      else:
        results = []

    return [ RemoteNode(self.store, node['metric_path'], node['isLeaf']) for node in results ]


class RemoteNode:
  context = {}

  def __init__(self, store, metric_path, isLeaf):
    self.store = store
    self.fs_path = None
    self.metric_path = metric_path
    self.real_metric = metric_path
    self.name = metric_path.split('.')[-1]
    self.__isLeaf = isLeaf

  def fetch(self, startTime, endTime):
    if not self.__isLeaf:
      return []

    query_params = [
      ('target', self.metric_path),
      ('pickle', 'true'),
      ('from', str( int(startTime) )),
      ('until', str( int(endTime) ))
    ]
    query_string = urlencode(query_params)

    connection = HTTPConnectionWithTimeout(self.store.host)
    connection.timeout = self.store.timeout
    connection.request('GET', '/render/?' + query_string)
    response = connection.getresponse()
    assert response.status == 200, "Failed to retrieve remote data: %d %s" % (response.status, response.reason)
    rawData = response.read()

    seriesList = pickle.loads(rawData)
    assert len(seriesList) == 1, "Invalid result: seriesList=%s" % str(seriesList)
    series = seriesList[0]

    timeInfo = (series['start'], series['end'], series['step'])
    return (timeInfo, series['values'])

  def isLeaf(self):
    return self.__isLeaf


# This is a hack to put a timeout in the connect() of an HTTP request.
# Python 2.6 supports this already, but many Graphite installations
# are not on 2.6 yet.

class HTTPConnectionWithTimeout(httplib.HTTPConnection):
  timeout = 30

  def connect(self):
    msg = "getaddrinfo returns an empty list"
    for res in socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM):
      af, socktype, proto, canonname, sa = res
      try:
        self.sock = socket.socket(af, socktype, proto)
        try:
          self.sock.settimeout( float(self.timeout) ) # default self.timeout is an object() in 2.6
        except:
          pass
        self.sock.connect(sa)
        self.sock.settimeout(None)
      except socket.error, msg:
        if self.sock:
          self.sock.close()
          self.sock = None
          continue
      break
    if not self.sock:
      raise socket.error, msg
