"""Priority Queues, quicksort selection and n-way merge based on binary heaps.

Based on source and notes in the documentation of ``heapq``, see:
http://docs.python.org/library/heapq.html"""

from operator import itemgetter
include "constants.pxi"

DEF INVALID = 0

cdef class Entry:
	def getkey(self):
		return self.key

	def getvalue(self):
		return self.value


cdef inline bint cmpfun(Entry a, Entry b):
	""" Generic comparison function for Entry objects. """
	return (a.value < b.value or (a.value == b.value and a.count < b.count))


cdef inline bint doublecmpfun(Entry a, Entry b):
	""" Comparison function for Entry objects containing C doubles.
	Faster than going through __richcmp__ of Python object. """
	return (PyFloat_AS_DOUBLE(a.value) < PyFloat_AS_DOUBLE(b.value)
		or (PyFloat_AS_DOUBLE(a.value) == PyFloat_AS_DOUBLE(b.value)
		and a.count < b.count))


@cython.final
cdef class Agenda:
	"""Priority Queue implemented with array-based n-ary heap.

	Implements decrease-key and remove operations by marking entries as
	invalid. Provides dictionary-like interface.

	Can be initialized with an iterable; order of equivalent values remains and
	the best priorities are retained on duplicate keys. """
	def __init__(self, iterable=None):
		cdef Entry entry, oldentry
		self.counter = 1
		self.length = 0
		self.heap = []
		self.mapping = {}
		if iterable:
			for k, v in iterable:
				entry = new_Entry(k, v, self.counter)
				if k in self.mapping:
					oldentry = <Entry>self.mapping[k]
					if cmpfun(entry, oldentry):
						oldentry.count = INVALID
						self.mapping[k] = entry
				else:
					self.mapping[k] = entry
					self.counter += 1
				self.heap.append(entry)
			self.length = len(self.mapping)
			heapify(self.heap, cmpfun)

	cdef void setitem(self, key, value):
		""" Like agenda[key] = value, but bypass Python API. """
		cdef Entry oldentry, entry
		if key in self.mapping:
			oldentry = <Entry>self.mapping[key]
			entry = <Entry>Entry.__new__(Entry)
			entry.key = key
			entry.value = value
			entry.count = oldentry.count
			self.mapping[key] = entry
			heappush(self.heap, entry, cmpfun)
			oldentry.count = INVALID
		else:
			self.counter += 1
			self.length += 1
			entry = <Entry>Entry.__new__(Entry)
			entry.key = key
			entry.value = value
			entry.count = self.counter
			self.mapping[key] = entry
			heappush(self.heap, entry, cmpfun)

	cdef void setifbetter(self, key, value):
		""" Sets an item, but only if item is new or has lower score.
		Equivalent to:
		if if key not in agenda or val < agenda[key]:
			agenda[key] = val """
		cdef Entry oldentry
		if key in self.mapping:
			oldentry = <Entry>self.mapping[key]
			if value >= oldentry.value:
				return
		self.setitem(key, value)

	cdef getitem(self, key):
		""" Like agenda[key], but bypass Python API. """
		cdef Entry entry
		entry = <Entry>self.mapping[key]
		return entry.value

	cdef object replace(self, key, value):
		""" :returns: current value for key, and also change its value.

		Equivalent to vv = d[k]; d[k] = v; return vv """
		cdef Entry entry, oldentry = <Entry>self.mapping[key]
		entry = <Entry>Entry.__new__(Entry)
		entry.key = key
		entry.value = value
		entry.count = oldentry.count
		self.mapping[key] = entry
		heappush(self.heap, entry, cmpfun)
		oldentry.count = INVALID
		return oldentry.value

	cdef Entry peekentry(self):
		""" Get the current best entry, while keeping it on the agenda. """
		cdef Entry entry
		cdef Py_ssize_t n = PyList_GET_SIZE(self.heap)
		if n == 0:
			raise IndexError("peek at empty heap")
		entry = <Entry>(self.heap[0])
		while entry.count == 0:
			if n == 1:
				raise IndexError("peek at empty heap")
			#replace first element with last element
			self.heap[0] = self.heap.pop()
			#and restore heap invariant
			siftdown(self.heap, 0, cmpfun)
			n -= 1
			entry = <Entry>(self.heap[0])
		return entry

	cdef Entry popentry(self):
		""" like popitem(), but avoids tuple construction by returning an Entry
		object """
		cdef Entry entry = <Entry>heappop(self.heap, cmpfun)
		while not entry.count:
			entry = <Entry>heappop(self.heap, cmpfun)
		del self.mapping[entry.key]
		self.length -= 1
		return entry

	cdef bint contains(self, key):
		""" Like `key in agenda`, but bypass the Python API. """
		return key in self.mapping

	def peekitem(self):
		""" Get the current best (key, value) pair, while keeping it on the
		agenda. """
		cdef Entry entry = self.peekentry()
		return entry.key, entry.value

	# standard dict() methods
	def pop(self, key):
		""" :returns: value for agenda[key] and remove it. """
		cdef Entry entry
		if key is None:
			return self.popentry().value
		entry = <Entry>(self.mapping.pop(key))
		entry.count = INVALID
		self.length -= 1
		return entry.value

	def popitem(self):
		""" :returns: best scoring (key, value) pair; removed from agenda. """
		cdef Entry entry = self.popentry()
		return entry.key, entry.value

	def __delitem__(self, key):
		""" Remove key from heap. """
		(<Entry>self.mapping[key]).count = INVALID
		self.length -= 1
		del self.mapping[key]

	def update(self, *a, **kw):
		""" Change score of items given a sequence of (key, value) pairs. """
		for b in a:
			for k, v in b:
				self[k] = v
		for k, v in kw.items():
			self[k] = v

	def clear(self):
		""" Remove all items from agenda. """
		self.counter = 1
		del self.heap[:]
		self.mapping.clear()

	def __repr__(self):
		return '%s({%s})' % (self.__class__.__name__, ", ".join(
				['%r: %r' % ((<Entry>a).key, (<Entry>a).value)
				for a in self.heap if (<Entry>a).count]))

	def __contains__(self, key):
		return key in self.mapping

	def __getitem__(self, key):
		return self.getitem(key)

	def __setitem__(self, key, value):
		self.setitem(key, value)

	def __str__(self):
		return self.__repr__()

	def __iter__(self):
		return iter(self.mapping)

	def __len__(self):
		return self.length

	def __nonzero__(self):
		return self.length != 0

	def keys(self):
		""" :returns: keys in agenda. """
		return self.mapping.keys()

	def values(self):
		""" :returns: values in agenda. """
		return map(Entry.getvalue, self.mapping.values())

	def items(self):
		""" :returns: (key, value) pairs in agenda. """
		return zip(self.keys(), self.values())


@cython.final
cdef class DoubleAgenda:
	"""Priority Queue where priorities are C doubles.

	Implements decrease-key and remove operations by marking entries as
	invalid. Provides dictionary-like interface.

	Can be initialized with an iterable; order of equivalent values
	remains and the best priorities are retained on duplicate keys.

	This version is specialized to be used as agenda with C doubles as
	priorities (values); keys are hashable Python objects."""
	def __init__(self, iterable=None):
		cdef Entry entry, oldentry
		self.counter = 1
		self.length = 0
		self.heap = []
		self.mapping = {}
		if iterable:
			for k, v in iterable:
				entry = new_Entry(k, v, self.counter)
				if k in self.mapping:
					oldentry = <Entry>self.mapping[k]
					if doublecmpfun(entry, oldentry):
						oldentry.count = INVALID
						self.mapping[k] = entry
				else:
					self.mapping[k] = entry
					self.counter += 1
				self.heap.append(entry)
			self.length = len(self.mapping)
			heapify(self.heap, doublecmpfun)

	cdef double getitem(self, key):
		""" Like agenda[key], but bypass Python API. """
		cdef Entry entry
		entry = <Entry>self.mapping[key]
		return PyFloat_AS_DOUBLE(entry.value)

	cdef inline void setifbetter(self, key, double value):
		""" sets an item, but only if item is new or has lower score """
		cdef Entry oldentry
		if key in self.mapping:
			oldentry = <Entry>self.mapping[key]
			if value >= PyFloat_AS_DOUBLE(oldentry.value):
				return
		self.setitem(key, value)

	cdef double replace(self, key, double value):
		""" return current value for key, and also change its value.
		equivalent to vv = d[k]; d[k] = v; return vv """
		cdef Entry entry, oldentry = <Entry>self.mapping[key]
		entry = <Entry>Entry.__new__(Entry)
		entry.key = key
		entry.value = value
		entry.count = oldentry.count
		self.mapping[key] = entry
		self.heap.append(entry)
		siftup(self.heap, 0, PyList_GET_SIZE(self.heap) - 1, doublecmpfun)
		oldentry.count = INVALID
		return PyFloat_AS_DOUBLE(oldentry.value)

	# the following are identical except for `doublecmpfun`
	cdef Entry popentry(self):
		""" like popitem, but avoids tuple construction by returning an Entry
		object """
		cdef Entry entry = <Entry>heappop(self.heap, doublecmpfun)
		while not entry.count:
			entry = <Entry>heappop(self.heap, doublecmpfun)
		del self.mapping[entry.key]
		self.length -= 1
		return entry

	cdef Entry peekentry(self):
		""" Get the current best entry, while keeping it on the agenda. """
		cdef Entry entry
		cdef Py_ssize_t n = PyList_GET_SIZE(self.heap)
		if n == 0:
			raise IndexError("peek at empty heap")
		entry = <Entry>(self.heap[0])
		while entry.count == 0:
			if n == 1:
				raise IndexError("peek at empty heap")
			#replace first element with last element
			self.heap[0] = self.heap.pop()
			#and restore heap invariant
			siftdown(self.heap, 0, doublecmpfun)
			n -= 1
			entry = <Entry>(self.heap[0])
		return entry

	cdef inline void setitem(self, key, double value):
		""" Like agenda[key] = value, but bypass Python API. """
		cdef Entry oldentry, entry
		if key in self.mapping:
			oldentry = <Entry>self.mapping[key]
			entry = <Entry>Entry.__new__(Entry)
			entry.key = key
			entry.value = value
			entry.count = oldentry.count
			self.mapping[key] = entry
			self.heap.append(entry)
			siftup(self.heap, 0, PyList_GET_SIZE(self.heap) - 1, doublecmpfun)
			oldentry.count = INVALID
		else:
			self.counter += 1
			self.length += 1
			entry = <Entry>Entry.__new__(Entry)
			entry.key = key
			entry.value = value
			entry.count = self.counter
			self.mapping[key] = entry
			self.heap.append(entry)
			siftup(self.heap, 0, PyList_GET_SIZE(self.heap) - 1, doublecmpfun)

	# identical to Agenda() methods
	cdef bint contains(self, key):
		""" Like `key in agenda`, but bypass the Python API. """
		return key in self.mapping

	def pop(self, key):
		""" :returns: value for agenda[key] and remove it. """
		cdef Entry entry
		if key is None:
			return self.popentry().value
		entry = <Entry>(self.mapping.pop(key))
		entry.count = INVALID
		self.length -= 1
		return entry.value

	def popitem(self):
		""" :returns: best scoring (key, value) pair, removed from agenda. """
		cdef Entry entry = self.popentry()
		return entry.key, entry.value

	def __delitem__(self, key):
		(<Entry>self.mapping[key]).count = INVALID
		self.length -= 1
		del self.mapping[key]

	def update(self, *a, **kw):
		""" Change score of items given a sequence of (key, value) pairs. """
		for b in a:
			for k, v in b:
				self[k] = v
		for k, v in kw.items():
			self[k] = v

	def clear(self):
		""" Remove all items from agenda. """
		self.counter = 1
		del self.heap[:]
		self.mapping.clear()

	def __repr__(self):
		return '%s({%s})' % (self.__class__.__name__, ", ".join(
				['%r: %r' % ((<Entry>a).key, (<Entry>a).value)
				for a in self.heap if (<Entry>a).count]))

	def __contains__(self, key):
		return key in self.mapping

	def __getitem__(self, key):
		return self.getitem(key)

	def __setitem__(self, key, value):
		self.setitem(key, value)

	def __str__(self):
		return self.__repr__()

	def __iter__(self):
		return iter(self.mapping)

	def __len__(self):
		return self.length

	def __nonzero__(self):
		return self.length != 0

	def keys(self):
		""" :returns: keys in agenda. """
		return self.mapping.keys()

	def values(self):
		""" :returns: values in agenda. """
		return map(Entry.getvalue, self.mapping.values())

	def items(self):
		""" :returns: (key, value) pairs in agenda. """
		return zip(self.keys(), self.values())


def f(x):
	return x


#A quicksort nsmallest implementation.
cdef list nsmallest(int n, object iterable, key=f):
	""" Return an _unsorted_ list of the n smallest items in a list. """
	cdef list items = list(iterable)
	if len(items) > 1:
		quickfindfirstk(items, 0, len(items) - 1, n, key)
	return items[:n]


cdef inline void quickfindfirstk(list items, int left, int right, int k, key):
	""" quicksort k-best selection """
	# select pivot index between left and right
	# middle between left & right
	cdef int pivot = left + (right - left) // 2
	cdef int pivotnewindex = partition(items, left, right, pivot, key)
	if pivotnewindex > k:
		if pivotnewindex - 1 > left:
			# new condition
			quickfindfirstk(items, left, pivotnewindex - 1, k, key)
	elif pivotnewindex < k:
		if right > pivotnewindex + 1:
			quickfindfirstk(items, pivotnewindex + 1, right, k, key)


cdef inline int partition(list items, int left, int right, int pivot, key):
	pivotvalue = key(items[pivot])
	# Move pivot to end
	items[pivot], items[right] = items[right], items[pivot]
	cdef int i, storeindex = left
	for i in range(left, right):
		if key(items[i]) < pivotvalue:
			items[i], items[storeindex] = items[storeindex], items[i]
			storeindex += 1
	# Move pivot to its final place
	items[storeindex], items[right] = items[right], items[storeindex]
	return storeindex


# heap operations (adapted from heapq)
cdef inline Entry heappop(list heap, CmpFun cmpfun):
	cdef Py_ssize_t n = PyList_GET_SIZE(heap)
	cdef Entry entry
	if n == 0:
		raise IndexError("pop from empty heap")
	elif n == 1:
		entry = <Entry>heap.pop()
	else:
		#replace first element with last element and restore heap invariant
		entry = <Entry>(PyList_GET_ITEM(heap, 0))
		heap[0] = heap.pop()
		siftdown(heap, 0, cmpfun)
	return entry


cdef inline void heappush(list heap, Entry entry, CmpFun cmpfun):
	# place at the end and swap with parents until heap invariant holds
	heap.append(entry)
	siftup(heap, 0, PyList_GET_SIZE(heap) - 1, cmpfun)


cdef inline void heapify(list heap, CmpFun cmpfun):
	""" Transform list into a heap, in-place, in O(len(heap)) time. """
	cdef int i
	for i in range(PyList_GET_SIZE(heap) // HEAP_ARITY, -1, -1):
		siftdown(heap, i, cmpfun)


# shifts only apply for binary tree
cdef inline int _parent(int i):
	return (i - 1) // HEAP_ARITY
	#return (i - 1) >> 1


cdef inline int _left(int i):
	return i * HEAP_ARITY + 1
	#return (i << 1) + 1


cdef inline int _right(int i):
	""" for documentation purposes; not used. """
	return i * HEAP_ARITY + 2
	#return (i + 1) << 1


def getparent(i):
	""" Python version of Cython-only _parent() function. """
	return (i - 1) // HEAP_ARITY


cdef inline void siftdown(list heap, int pos, CmpFun cmpfun):
	cdef int startpos = pos, childpos = _left(pos), rightpos
	cdef int endpos = PyList_GET_SIZE(heap)
	cdef Entry newitem = <Entry>PyList_GET_ITEM(heap, pos)
	while childpos < endpos:
		for rightpos in range(childpos + 1, childpos + HEAP_ARITY):
			if (rightpos < endpos and
				cmpfun(<Entry>(PyList_GET_ITEM(heap, rightpos)),
					<Entry>(PyList_GET_ITEM(heap, childpos)))):
				childpos = rightpos
		heap[pos] = <Entry>PyList_GET_ITEM(heap, childpos)
		pos = childpos
		childpos = _left(pos)
	heap[pos] = newitem
	siftup(heap, startpos, pos, cmpfun)


cdef inline void siftup(list heap, int startpos, int pos, CmpFun cmpfun):
	cdef int parentpos
	cdef Entry parent, newitem = <Entry>PyList_GET_ITEM(heap, pos)
	while pos > startpos:
		parentpos = _parent(pos)
		parent = <Entry>PyList_GET_ITEM(heap, parentpos)
		if cmpfun(parent, newitem):
			break
		heap[pos] = parent
		pos = parentpos
	heap[pos] = newitem


def identity(x):
	return x


def nwaymerge(iterables, key=None):
	"""Generator that performs an n-way merge of sorted iterables.

	NB: while a sort key may be specified, the individual iterables must
	already be sorted with this key.

	Algorithm based on:
	http://stackoverflow.com/questions/5055909/algorithm-for-n-way-merge"""
	cdef list heap = []
	cdef unsigned long cnt = 1
	if key is None:
		key = identity
	iterables = [iter(it) for it in iterables]

	for items in iterables:
		try:
			item = next(items)
		except StopIteration:
			pass
		else:
			heappush(heap,
					new_Entry((item, items), key(item), cnt),
					cmpfun)
			cnt += 1

	while(heap):
		smallest = heappop(heap, cmpfun)
		yield smallest.getkey()[0]
		try:
			item = next(smallest.getkey()[1])
		except StopIteration:
			pass
		else:  # add next element from current iterable
			heappush(heap,
					new_Entry((item, smallest.getkey()[1]), key(item), cnt),
					cmpfun)
			cnt += 1
