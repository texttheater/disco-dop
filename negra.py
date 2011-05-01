from nltk.corpus.reader.api import CorpusReader, SyntaxCorpusReader
from nltk.corpus.reader.util import read_regexp_block, StreamBackedCorpusView, concat
from nltk import Tree
import re

BOS = re.compile("^#BOS.*\n")
EOS = re.compile("^#EOS")
WORD, LEMMA, TAG, MORPH, FUNC, PARENT = range(6)

class NegraCorpusReader(SyntaxCorpusReader):
	def __init__(self, root, fileids, encoding=None, n=6, headorder=False, headfinal=False, reverse=False, unfold=False):
		""" n=6 for files with 6 columns, n=5 for files with 5 columns (no lemmas)
			headfinal: whether to put the head in final or in frontal position
			reverse: the head is made final/frontal by reversing everything before or after the head. 
				when true, the side on which the head is will be the reversed side"""
		#fixme: autodetect this, or put stuff in dictionaries instead of lists
		if n == 5: self.d = 1	
		else: self.d = 0
		self.headorder = headorder; self.headfinal = headfinal
		self.reverse = reverse; self.unfold = unfold
		CorpusReader.__init__(self, root, fileids, encoding)
	def _parse(self, s):
		d = self.d
		def getchildren(parent, children):
			results = []; head = None
			for n,a in children[parent]:
				# n is the index in the block to record word indices
				if a[WORD][0] == "#": #nonterminal
					results.append(Tree(a[TAG-d], getchildren(a[WORD][1:], children)))
					results[-1].source = a
				else: #terminal
					results.append(Tree(a[TAG-d], [n]))
					results[-1].source = a
				if head is None and "HD" in a[FUNC-d].split("-"): head = results[-1]
			# roughly order constituents by order in sentence
			results.sort(key=lambda a: a.leaves()[0])
			if head is None or not self.headorder: return results
			head = results.index(head)
			# everything until the head is reversed and prepended to the rest,
			# leaving the head as the first element
			if self.headfinal:
				if self.reverse:
					# head final, reverse rhs: A B C^ D E => A B E D C^
					return results[:head] + results[head:][::-1]
				else:
					# head final, no reverse:  A B C^ D E => D E A B C^
					#return sorted(results[head+1:] + results[:head]) + results[head:head+1]
					# head final, reverse lhs:  A B C^ D E => E D A B C^
					return results[head+1:][::-1] + results[:head+1]
			else:
				if self.reverse:
					# head first, reverse lhs: A B C^ D E => C^ B A D E
					return results[:head+1][::-1] + results[head+1:]
				else:
					# head first, reverse rhs: A B C^ D E => C^ D E B A
					return results[head:] + results[:head][::-1]
		children = {}
		for n,a in enumerate(s):
			children.setdefault(a[PARENT-d], []).append((n,a))
		if self.unfold:
			return unfold(Tree("ROOT", getchildren("0", children)))
		return Tree("ROOT", getchildren("0", children))
	def _word(self, s):
		return [a[WORD] for a in s if a[WORD][0] != "#"]
	def _tag(self, s, ignore):
		return [(a[WORD], a[TAG-self.d]) for a in s if a[WORD][0] != "#"]
	def _read_block(self, stream):
		return [[line.split() for line in block.splitlines()[1:]]
				for block in read_regexp_block(stream, BOS, EOS)]
			# didn't seem to help:
			#for b in map(lambda x: read_regexp_block(stream, BOS, EOS), range(1000)) for block in b]
	def blocks(self):
		""" Return a list of blocks, taken verbatim from the treebank file."""
		def reader(stream):
			result = read_regexp_block(stream, BOS, EOS)
			return [re.sub(BOS,"", result[0])] if result else []
		return concat([StreamBackedCorpusView(fileid, reader, encoding=enc)
					for fileid, enc in self.abspaths(self._fileids, True)])

# generalizations suggested by SyntaxGeneralizer of TigerAPI
# however, instead of renaming, we introduce unary productions
# POS tags
tonp = "NN NNE PNC PRF PDS PIS PPER PPOS PRELS PWS".split()
topp = "PROAV PWAV".split()  # ??
toap = "ADJA PDAT PIAT PPOSAT PRELAT PWAT PRELS".split()
toavp = "ADJD ADV".split()

tagtoconst = {}
for a in tonp: tagtoconst[a] = "NP"
#for a in toap: tagtoconst[a] = "AP"
#for a in toavp: tagtoconst[a] = "AVP"

# phrasal categories
tonp = "CNP NM PN".split()
topp = "CPP".split()
toap = "MTA CAP".split()
toavp = "AA CAVP".split()
unaryconst = {}
for a in tonp: unaryconst[a] = "NP"

def unfold(tree):
	""" Unfold redundancies and perform other transformations introducing
	more hierarchy in the phrase-structure annotation based on 
	grammatical functions.
	"""
	original = tree.copy(Tree); current = tree # for debugging
	def function(tree):
			if hasattr(tree, "source"): return tree.source[FUNC - 1 if len(tree.source)==5 else 0].split("-")[0]
	# un-flatten PPs
	addtopp = "AC MO".split()
	for pp in tree.subtrees(lambda n: n.node == "PP"):
		ac = [a for a in pp if function(a) in addtopp]
		nk = [a for a in pp if function(a) not in addtopp]
		if ac and nk and (len(nk) > 1 or nk[0].node not in "NP PN".split()):
			pp[:] = ac + [Tree("NP", nk)]
	# introduce DPs
	for np in list(tree.subtrees(lambda n: n.node == "NP")):
		if np[0].node == "ART":
			np.node = "DP"
			if np[1].node != "PN": np[:] = [np[0], Tree("NP", np[1:])]
	# introduce finite VP at S level, collect objects and modifiers
	# introduce new S level for discourse markers
	newlevel = "DM".split()
	addtovp = "HD AC DA MO NG OA OA2 OC OG PD VO SVP".split()
	labels = [a.node for a in tree]
	def finitevp(s):
		if any(x.node.startswith("V") and x.node.endswith("FIN") for x in s if isinstance(x, Tree)):
			vp = Tree("VP", [a for a in s if function(a) in addtovp])
			if len(vp) != 1 or vp[0].node != "VP":
				s[:] = [a for a in s if function(a) not in addtovp] + [vp]
	toplevel_s = []
	if "S" in labels:
		# multiple S ?
		s = tree[labels.index("S")]
		toplevel_s = [s]
		if function(s[0]) in newlevel:
			s[:] = [s[0], Tree("S", s[1:])]
			toplevel_s = [s[1]]
	elif "CS" in labels:
		cs = tree[labels.index("CS")]
		toplevel_s = [a for a in cs if a.node == "S"]
	map(finitevp, toplevel_s)
	# introduce POS tag for particle verbs
	for a in tree.subtrees(lambda n: "SVP" in map(function, n)):
		svp = [x for x in a if function(x) == "SVP"].pop()
		#apparently there can be a _verb_ particle without a verb. headlines? annotation mistake?
		if "HD" in map(function, a):
			hd = [x for x in a if function(x) == "HD"].pop()
			if hd.node != a.node:
				particleverb = Tree(hd.node, [hd, svp])
				a[:] = [particleverb if function(x) == "HD" else x for x in a if function(x) != "SVP"]
	# introduce SBAR level
	sbarfunc = "CP".split()
	for s in list(tree.subtrees(lambda n: n.node == "S" and function(n[0]) in sbarfunc and n not in toplevel_s)):
		if len(s) > 1:
			s.node = "SBAR"
			s[:] = [s[0], Tree("S", s[1:])]
	# restore linear precedence ordering
	for a in tree.subtrees(lambda n: len(n) > 1): a.sort(key=lambda n: n.leaves())
	# do head order etc.
	return tree
	# introduce phrasal projections for single tokens
	for a in tree.treepositions("leaves"):
		tag = tree[a[:-1]]   # e.g. NN
		const = tree[a[:-2]] # e.g. S
		if tag.node in tagtoconst and const.node != tagtoconst[tag.node]:
			newconst = Tree(tagtoconst[tag.node], [tag])
			const[a[-2]] = newconst
	return tree

def fold(tree):
	""" Undo the transformations performed by unfold. Do not apply twice (would remove VPs which shouldn't be). """
	# remove DPs
	for dp in tree.subtrees(lambda n: n.node == "DP"):
			dp.node = "NP"
			if dp[1].node == "NP": dp[:] = dp[:1] + dp[1][:]
	# flatten PPs
	for pp in tree.subtrees(lambda n: n.node == "PP"):
		if "NP" in (a.node for a in pp): # and (pp[1][0].node == "ART" or pp[0].node.endswith("ART")): # except when VP in NP
			#ensure NP is in last position
			pp.sort(key=lambda n: n.node == "NP")
			pp[:] = pp[:-1] + pp[-1][:]
	# merge extra S level
	for sbar in list(tree.subtrees(lambda n: n.node == "SBAR" or (n.node == "S" and len(n) == 2 and n[0].node == "PTKANT" and n[1].node == "S"))):
		sbar.node = "S"
		sbar[:] = sbar[:1] + sbar[1][:]
	# merge finite VP with S level
	def mergevp(s):
		for vp in (n for n,a in enumerate(s) if a.node == "VP"):
			if any(a.node.endswith("FIN") for a in s[vp]):
				s[:] = s[:vp] + s[vp][:] + s[vp+1:]
	if any(a.node == "S" for a in tree):
		map(mergevp, [a for a in tree if a.node == "S"])
	elif any(a.node == "CS" for a in tree):
		map(mergevp, [s for cs in tree for s in cs if cs.node == "CS" and s.node == "S"])
	# remove constituents for particle verbs
	# get the grandfather of each verb particle
	for a in list(tree.subtrees(lambda n: any("PTKVZ" in (x.node for x in m if isinstance(x, Tree)) for m in n if isinstance(m, Tree)))):
		for n,b in enumerate(a):
			if len(b) == 2 and b.node.startswith("V") and "PTKVZ" in (c.node for c in b if isinstance(c, Tree)) and any(c.node == b.node for c in b):
				a[n:n+1] = b[:]
	# remove phrasal projections for single tokens
	for a in tree.treepositions("leaves"):
		tag = tree[a[:-1]]    # NN
		const = tree[a[:-2]]  # NP
		parent = tree[a[:-3]] # PP
		if len(const) == 1 and tag.node in tagtoconst and const.node == tagtoconst[tag.node]:
			parent[a[-3]] = tag
			del const
	# restore linear precedence ordering
	for a in tree.subtrees(lambda n: len(n) > 1): a.sort(key=lambda n: n.leaves())
	return tree

def bracketings(tree):
        return [(a.node, tuple(sorted(a.leaves()))) for a in tree.subtrees(lambda t: t.height() > 2)]

def main():
	from rcgrules import canonicalize
	from itertools import count
	print "normal"
	#n = NegraCorpusReader(".", "sample2\.export")
	n = NegraCorpusReader("../rparse", "tiger3600proc\.export", n=5, headorder=False)
	"""
	for a in n.parsed_sents(): print a
	for a in n.tagged_sents(): print " ".join("/".join(x) for x in a)
	for a in n.sents(): print " ".join(a)
	for a in n.blocks(): print a
	print "\nunfolded"
	"""
	#nn = NegraCorpusReader(".", "sample2\.export", unfold=True)
	nn = NegraCorpusReader("../rparse", "tiger3600proc\.export", n=5, unfold=True)
	correct = exact = d = 0
	for a,b,c in zip(n.parsed_sents(), nn.parsed_sents(), n.sents()):
		#if len(c) > 15: continue
		foldb = fold(b.copy(True))
		b1 = bracketings(canonicalize(a))
		b2 = bracketings(canonicalize(foldb))
		z = -1
		if b1 != b2 or d == z:
			precision = len(set(b1) & set(b2)) / float(len(set(b1)))
			recall = len(set(b1) & set(b2)) / float(len(set(b2)))
			if precision != 1.0 or recall != 1.0 or d == z:
				print d, " ".join(":".join((str(n),a)) for n,a in enumerate(c))
				print "no match", precision, recall
				print len(b1), len(b2), set(b2) - set(b1), set(b1) - set(b2)
				print a
				print foldb
				print b
			else:
				correct += 1
		else:
			exact += 1
			correct += 1
		d += 1
	print "matches", correct, "/", d, 100 * correct / float(d), "%"
	print "exact", exact
if __name__ == '__main__': main()
