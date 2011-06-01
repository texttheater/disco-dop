# Priority Queue based on binary heap which implements decrease-key
# by marking entries as invalid
# Based on notes in http://docs.python.org/library/heapq.html

from heapq import heappush, heappop, heapify
from items import Edge, ChartItem
INVALID = 0

class Entry(object):
	__slots__ = ('key', 'value', 'count')
	def __init__(self, key, value, count):
		self.key = key			#the `task'
		self.value = value		#the priority
		self.count = count		#unqiue identifier to resolve ties
	'''
	def __cmp__(self, other):
		if self.count == other.count: return 0
		if self.value[0][0] < other.value[0][0] or (self.value[0][0] == other.value[0][0] and self.count < other.count): return -1
		return 1
	'''
	def __eq__(self, other):
		return self.count == other.count
	def __lt__(self, other):
		return self.value.inside < other.value.inside or (self.value.inside == other.value.inside and self.count < other.count)
	def __le__(self, other):
		return self.value.inside < other.value.inside or (self.value.inside == other.value.inside and self.count <= other.count)
	def __hash__(self):
		return hash((self.key, (self.value, self.count)))

class heapdict(object):
	def __init__(self, iterable=None):
		self.heap = []						# the priority queue list
		self.counter = 1					# unique sequence count
		self.mapping = {}					# mapping of keys to entries
		if iterable:
			self.heap = [Entry(k, v, n + 1)
							for n, (k,v) in enumerate(dict(iterable).items())]
			heapify(self.heap)
			self.mapping = dict((entry.key, entry) for entry in self.heap)
			self.counter += len(self.heap)

	def __setitem__(self, key, value):
		if key in self.mapping:
			oldentry = self.mapping[key]
			entry = Entry(key, value, oldentry.count)
			self.mapping[key] = entry
			heappush(self.heap, entry)
			oldentry.count = INVALID
		else:
			entry = Entry(key, value, self.counter)
			self.counter += 1
			self.mapping[key] = entry
			heappush(self.heap, entry)
		return None

	def __getitem__(self, key):
		return self.mapping[key].value

	def __delitem__(self, key):
		self.mapping.pop(key).count = INVALID

	def __contains__(self, key):
		return key in self.mapping

	def __len__(self):
		return len(self.mapping)

	def keys(self):
		return self.mapping.keys()

	def values(self):
		return map(lambda x: x.value, self.mapping.values())

	def items(self):
		return zip(self.keys(), self.values())

	def peekitem(self):
		while self.heap[0].count is INVALID:
			entry = heappop(self.heap)
			try: del self.mapping[entry.key]
			except KeyError: pass
		return self.heap[0].key, self.heap[0].value

	def popitem(self):
		entry = heappop(self.heap)
		try: del self.mapping[entry.key]
		except KeyError: pass
		while entry.count is INVALID:
			entry = heappop(self.heap)
			try: del self.mapping[entry.key]
			except KeyError: pass
		return entry.key, entry.value

	def pop(self, key):
		entry = self.mapping.pop(key)
		entry.count = INVALID
		return entry.value

	def clear(self):
		self.counter = 1
		del self.heap[:]
		self.mapping.clear()

def mainpq():
	c = ChartItem(0, 0)
	n = ChartItem(0, 0)
	h = heapdict([(ChartItem(0,0), Edge(0.0, 0.0, c, n))])
	assert h.popitem() == (ChartItem(0, 0), Edge(0.0, 0.0, c, n))
	assert len(h) == 0
	h[ChartItem(0, 0)] = Edge(0.0, 0.0, c, n)
	assert h.pop(ChartItem(0, 0)) == Edge(0.0, 0.0, ChartItem(0, 0), n)
	assert len(h) == 0
	h = heapdict()
	ee = Entry(ChartItem(0, 0), Edge(0.5, 0.0, ChartItem(0, 0), ChartItem(0, 0)), 1)
	e = Entry(ChartItem(0, 0), Edge(0.0, 0.0, ChartItem(0, 0), n), 1)
	assert e < ee
	assert e == e
	assert e <= e
	assert e <= ee
	assert hash(e) == hash((e.key, (e.value, e.count)))
	h[ChartItem(0, 0)] = Edge(0.0, 0.0, c, c)
	h[ChartItem(0, 0)] = Edge(0.0, 0.0, c, n)
	h[ChartItem(2, 0)] = Edge(0.0, 0.0, c, n)
	del h[ChartItem(2, 0)]
	assert ChartItem(2, 0) not in h
	assert ChartItem(2, 0) == ChartItem(2, 0)
	assert ChartItem(2, 0) <= ChartItem(2, 0)
	assert ChartItem(1, 0) <= ChartItem(2, 0)
	assert ChartItem(1, 0) < ChartItem(2, 0)
	v = h[ChartItem(0, 0)]
	assert v in h.values()
	assert h.keys() == [ChartItem(0, 0)]
	assert h.values() == [Edge(0.0, 0.0, c, n)]
	assert h.items() == [(ChartItem(0,0), Edge(0.0, 0.0, c, n))]
	assert h.peekitem() == (ChartItem(0, 0), Edge(0.0, 0.0, c, n))
	assert h.popitem() == (ChartItem(0, 0), Edge(0.0, 0.0, c, n))
	print 'it worked'

if __name__ == '__main__': mainpq()