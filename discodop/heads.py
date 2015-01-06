"""Functions related to finding the linguistic head of a constituent."""
from __future__ import division, print_function, absolute_import, \
		unicode_literals
import io
import re
from collections import defaultdict, Counter
from discodop.tree import Tree
from discodop import punctuation

FIELDS = tuple(range(8))
WORD, LEMMA, TAG, MORPH, FUNC, PARENT, SECEDGETAG, SECEDGEPARENT = FIELDS
HEADRULERE = re.compile(r'^(\S+)\s+(LEFT-TO-RIGHT|RIGHT-TO-LEFT)(?:\s+(.*))?$')


def ishead(tree):
	"""Test whether this node is the head of the parent constituent."""
	return getattr(tree, 'head', False)


def getheadpos(node):
	"""Get head word dominated by this node."""
	child = node
	while True:
		if not child:
			break
		if not isinstance(child[0], Tree):
			return child
		try:
			child = next(a for a in child if ishead(a))
		except StopIteration:
			break
	return None


def readheadrules(filename):
	"""Read a file containing heuristic rules for head assignment.

	Example line: ``s right-to-left vmfin vafin vaimp``, which means
	traverse siblings of an S constituent from right to left, the first child
	with a label of vmfin, vafin, or vaimp will be marked as head."""
	headrules = {}
	for line in io.open(filename, encoding='utf8'):
		line = line.strip().upper()
		if line and not line.startswith("%") and len(line.split()) > 2:
			try:
				label, direction, heads = HEADRULERE.match(line).groups()
			except AttributeError:
				print('no match:', line)
				raise
			if heads is None:
				heads = ''
			headrules.setdefault(label, []).append((direction, heads.split()))
	return headrules


def headfinder(tree, headrules, headlabels=frozenset({'HD'})):
	"""Use head finding rules to select one child of tree node as head."""
	candidates = [a for a in tree if getattr(a, 'source', None)
			and headlabels.intersection(a.source[FUNC].upper().split('-'))]
	if candidates:
		return candidates[0]
	children = tree
	for direction, heads in headrules.get(tree.label, []):
		if direction == 'LEFT-TO-RIGHT':
			children = tree
		elif direction == 'RIGHT-TO-LEFT':
			children = tree[::-1]
		else:
			raise ValueError('expected RIGHT-TO-LEFT or LEFT-TO-RIGHT.')
		for head in heads:
			for child in children:
				if (isinstance(child, Tree)
						and child.label.split('[')[0] == head):
					return child
	# default head is initial/last nonterminal (depending on direction)
	for child in children:
		if (isinstance(child, Tree)
				and not punctuation.ispunct(None, child.label)):
			return child


def ptbheadfinder(tree, headrules, headlabels=frozenset({'HD'}), dptb=False):
	"""PTB-specific head rules for co-ordination, NPs and WH elements."""
	head = None
	if tree.label == 'NP':
		if tree[-1].label == 'POS':
			head = tree[-1]
		else:
			for rhslabels in (
					{'NN', 'NNP', 'NNPS', 'NNS', 'NX', 'POS', 'JR'},
					{'NP'},
					{'$.', 'ADJP', 'PRN'},
					{'CD'},
					{'JJ', 'JJS', 'RB', 'QP'}):
				for a in reversed(tree):
					if a.label in rhslabels or (dptb
							and a.label.startswith('WH')
							and a.label[2:] in rhslabels):
						head = a
						break
				if head:
					break
			if head is None:
				head = tree[-1]
	else:
		head = headfinder(tree, headrules, headlabels)
	i = tree.index(head)
	if i >= 2:
		if tree[i - 1].label in {'CC', 'CONJP'}:
			for althead in tree[i - 2::-1]:
				if not punctuation.ispunct(althead.label, althead.label):
					return althead
	return head


def sethead(child):
	"""Mark node as head in an auxiliary field."""
	child.head = True


def saveheads(tree, tailmarker):
	"""Store head as grammatical function when inferrable from binarization."""
	if tailmarker:
		for node in tree.subtrees(lambda n: tailmarker in n.label):
			sethead(node)
	# assume head-outward binarization; the last binarized node has the head.
	for node in tree.subtrees(lambda n: '|<' in n.label
			and not any(child.label.startswith(
				n.label[:n.label.index('|<') + 2])
				for child in n)):
		sethead(node[-1])


def headstats(trees):
	"""Collect some information useful for writing headrules.

	- ``heads['NP']['NN'] ==`` number of times NN occurs as head of NP.
	- ``pos1['NP'][1] ==`` number of times head of NP is at position 1.
	- ``pos2`` is like pos1, but position is from the right.
	- ``unknown['NP']['NN'] ==`` number of times NP that does not have a head
		dominates an NN."""
	heads, unknown = defaultdict(Counter), defaultdict(Counter)
	pos1, pos2 = defaultdict(Counter), defaultdict(Counter)
	for tree in trees:
		for a in tree.subtrees(lambda x: len(x) > 1):
			for n, b in enumerate(a):
				if ishead(b):
					heads[a.label][b.label] += 1
					pos1[a.label][n] += 1
					pos2[a.label][len(a) - (n + 2)] += 1
					break
			else:
				unknown[a.label].update(b.label for b in a)
	return heads, unknown, pos1, pos2


__all__ = ['ishead', 'getheadpos', 'readheadrules', 'headfinder',
		'ptbheadfinder', 'sethead', 'saveheads', 'headstats']