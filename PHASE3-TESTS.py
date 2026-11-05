#!/usr/bin/env python3
"""VaultChain Phase III | Executable storage-engine implementation and tests.

TEST TOPIC
    AES-256-GCM ciphertext handling, adaptive cross-owner erasure coding,
    selective reconstruction, integrity, deletion and 6-of-4 node recovery.

SCOPE & EVIDENCE
    Single GitHub-ready file, organized in clear engine/test/benchmark sections.
    Node storage is in-memory. No real Google Drive or blockchain contracts.
    All demonstration/benchmark documents are ACTUAL AES-256-GCM ciphertext.
    Timed encoding, verification, commit, retrieval and repair are SEPARATED.
    Baselines include fixed and sorted cohorts, independent (6,4) RS and
    threefold replication, with each comparison's assumptions labeled.

RUN
    python -m pip install cryptography
    python test_vaultchain_phase3.py --quick --json phase3_results.json
    python test_vaultchain_phase3.py --json phase3_results.json

Python 3.10+; Python standard library + cryptography. No remote side effects.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import random
import statistics
import sys
from pathlib import Path
import time
import tracemalloc
import platform
import resource
import unittest
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError as exc:
    raise SystemExit("Missing dependency: python -m pip install cryptography") from exc

N = 6  # coded fragments per group
K = 4  # preferred number of independent source rows


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def client_encrypt(doc_id: str, plaintext: bytes, key: Optional[bytes] = None):
    """AEAD client boundary; returns (nonce+ciphertext+tag, private_key)."""
    key = key or AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    result = nonce + AESGCM(key).encrypt(nonce, plaintext, doc_id.encode())
    return result, key


def client_decrypt(doc_id: str, payload: bytes, key: bytes) -> bytes:
    return AESGCM(key).decrypt(payload[:12], payload[12:], doc_id.encode())


class InsufficientFragments(Exception): ...
class InvalidState(Exception): ...
class InsufficientCapacity(Exception): ...
class Unauthorized(Exception): ...
class Conflict(Exception): ...


class GF:
    """GF(256) lookup tables with AES polynomial 0x11B and primitive 0x03."""
    exp = [0] * 512
    log = [0] * 256
    lookup = {}

    @staticmethod
    def _slow_mul(a: int, b: int) -> int:
        result = 0
        while b:
            if b & 1:
                result ^= a
            a <<= 1
            if a & 256:
                a ^= 0x11B
            b >>= 1
        return result

    @classmethod
    def init(cls):
        x = 1
        for i in range(255):
            cls.exp[i] = x
            cls.log[x] = i
            x = cls._slow_mul(x, 3)
        assert x == 1
        for i in range(255, 512):
            cls.exp[i] = cls.exp[i - 255]

    @classmethod
    def mul(cls, a: int, b: int) -> int:
        return 0 if not a or not b else cls.exp[cls.log[a] + cls.log[b]]

    @classmethod
    def inv(cls, a: int) -> int:
        if a == 0:
            raise InvalidState('singular coding matrix')
        return cls.exp[255 - cls.log[a]]

    @classmethod
    def power(cls, a: int, n: int) -> int:
        return 1 if n == 0 else cls.exp[(cls.log[a] * n) % 255]

    @classmethod
    def byte_map(cls, c: int) -> bytes:
        if c not in cls.lookup:
            cls.lookup[c] = bytes(cls.mul(c, x) for x in range(256))
        return cls.lookup[c]


GF.init()


def generator(k: int) -> List[List[int]]:
    if not 2 <= k <= K:
        raise InvalidState('mixed rank must be between 2 and 4')
    return [[GF.power(row + 1, j) for j in range(k)] for row in range(N)]


def inverse(matrix: List[List[int]]) -> List[List[int]]:
    n = len(matrix)
    a = [list(row) + [int(j == i) for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = next((i for i in range(col, n) if a[i][col]), None)
        if pivot is None:
            raise InvalidState('insufficient independent coded rows')
        a[col], a[pivot] = a[pivot], a[col]
        coef = GF.inv(a[col][col])
        a[col] = [GF.mul(coef, x) for x in a[col]]
        for row in range(n):
            if row != col and a[row][col]:
                factor = a[row][col]
                a[row] = [x ^ GF.mul(factor, y) for x, y in zip(a[row], a[col])]
    return [row[n:] for row in a]


def linear_rows(coeff: List[List[int]], blocks: List[bytes]) -> List[bytes]:
    if len({len(b) for b in blocks}) != 1:
        raise InvalidState('source-row widths differ')
    width = len(blocks[0])
    answer = []
    for row in coeff:
        out = bytearray(width)
        for c, source in zip(row, blocks):
            if c == 0:
                continue
            src = source if c == 1 else source.translate(GF.byte_map(c))
            for i, val in enumerate(src):
                out[i] ^= val
        answer.append(bytes(out))
    return answer


def schedule_sizes(sizes: Dict[str, int], k: int = K):
    """Greedy k-distinct-owner stripe planning with sparse fallback.

    If complete no-padding mixing is feasible, preserves that feasibility
    while selecting large variable-width groups. Otherwise mixes any useful
    real four-owner portions and returns the true residual, never fake owners.
    """
    remaining = dict(sizes)
    groups = []
    while sum(v > 0 for v in remaining.values()) >= k:
        top = sorted((o for o, v in remaining.items() if v > 0),
                     key=lambda o: (-remaining[o], o))[:k]
        upper = min(remaining[o] for o in top)
        total = sum(remaining.values())
        feasible_now = total % k == 0 and max(remaining.values()) * k <= total

        def can_continue(w):
            after = {o: (v - w if o in top else v) for o, v in remaining.items()}
            t = sum(after.values())
            return t == 0 or (t % k == 0 and sum(v > 0 for v in after.values()) >= k
                              and max(after.values()) * k <= t)

        if feasible_now:
            lo, hi = 1, upper
            if can_continue(1):
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if can_continue(mid):
                        lo = mid
                    else:
                        hi = mid - 1
                width = lo
            else:
                width = upper
        else:
            width = upper
        if width <= 0:
            break
        for owner in top:
            remaining[owner] -= width
        groups.append((tuple(top), width))
    return groups, remaining


@dataclass(frozen=True)
class Span:
    doc: str
    owner: str
    offset: int
    real_length: int


@dataclass(frozen=True)
class Fragment:
    key: str
    node: int
    row: int
    digest: str
    size: int


@dataclass(frozen=True)
class CodingGroup:
    id: str
    lane: int
    mode: str
    members: Tuple[Span, ...]
    refs: Tuple[Fragment, ...]
    width: int
    rank: int


@dataclass(frozen=True)
class Document:
    owner: str
    length: int
    digest: str


@dataclass
class Transition:
    expected_epoch: int
    groups: Dict[str, CodingGroup]
    documents: Dict[str, Document]
    staged: Dict[str, bytes]
    active_nodes: Tuple[int, ...]
    joining_node: Optional[int] = None
    verified: bool = False
    binding: str = ''


class Engine:
    """In-memory simulated cloud-node pool; no document keys/plaintext stored."""
    def __init__(self, node_count=12, capacity=10_000_000):
        if node_count < N:
            raise InvalidState('six available nodes required by this coding profile')
        self.nodes = {i: {'capacity': capacity, 'active': True, 'objects': {}}
                      for i in range(node_count)}
        self.documents: Dict[str, Document] = {}
        self.groups: Dict[str, CodingGroup] = {}
        self.epoch = 0
        self.serial = 0
        self.ledger_available = True  # availability proxy, NOT a blockchain

    def active_nodes(self):
        return tuple(i for i, n in self.nodes.items() if n['active'])

    @staticmethod
    def lanes(nodes):
        nodes = tuple(nodes)
        if len(nodes) < N:
            raise InvalidState('insufficient distinct nodes')
        if len(nodes) % N == 0:
            return [nodes[i:i+N] for i in range(0, len(nodes), N)]
        return [tuple(nodes[(i+j) % len(nodes)] for j in range(N))
                for i in range(len(nodes))]

    def gid(self):
        self.serial += 1
        return f'g{self.serial:06d}'

    def create_group(self, lane, nodeset, rows, mode):
        """Rows: [(doc, owner, ciphertext_absolute_offset, ciphertext_bytes)]."""
        gid = self.gid()
        if mode == 'MIXED':
            if not (2 <= len(rows) <= K and len({r[1] for r in rows}) == len(rows)):
                raise InvalidState('genuine mixed group needs distinct source owners')
            blocks = [r[3] for r in rows]
            if not blocks or not blocks[0] or len({len(b) for b in blocks}) != 1:
                raise InvalidState('invalid mixed source widths')
            members = tuple(Span(d, o, offset, len(data)) for d, o, offset, data in rows)
        elif mode == 'STANDALONE':
            if len(rows) != 1 or not rows[0][3]:
                raise InvalidState('standalone group needs one nonempty document portion')
            d, o, offset, raw = rows[0]
            width = math.ceil(len(raw) / K)
            blocks = [raw[i*width:(i+1)*width].ljust(width, b'\0') for i in range(K)]
            members = tuple(Span(d, o, offset+i*width,
                                 max(0, min(width, len(raw) - i*width)))
                            for i in range(K))
        else:
            raise InvalidState('unknown coding mode')
        coded = linear_rows(generator(len(blocks)), blocks)
        stage = {}
        refs = []
        for r, coded_bytes in enumerate(coded):
            key = f'{gid}/fragment-{r}'
            stage[key] = coded_bytes
            refs.append(Fragment(key, nodeset[r], r, sha(coded_bytes), len(coded_bytes)))
        return CodingGroup(gid, lane, mode, members, tuple(refs), len(blocks[0]),
                           len(blocks)), stage

    def build(self, files: Dict[str, Tuple[str, bytes]], nodes):
        """Create a new placement epoch from ciphertext; preserve doc boundaries."""
        placement = self.lanes(nodes)
        queues = [defaultdict(deque) for _ in placement]
        for doc_id, (owner, ciphertext) in sorted(files.items()):
            if len(ciphertext) < len(placement):
                raise InvalidState('document cannot cover all nonempty placement lanes')
            base = 0
            q, r = divmod(len(ciphertext), len(placement))
            for lane in range(len(placement)):
                part = ciphertext[base:base+q+(lane < r)]
                queues[lane][owner].append([doc_id, base, part])
                base += len(part)
        groups = {}
        stage = {}
        for lane, nodeset in enumerate(placement):
            q = queues[lane]
            sizes = {owner: sum(len(item[2]) for item in parts)
                     for owner, parts in q.items()}
            selections, residual = schedule_sizes(sizes)
            for owners, width in selections:
                remaining = width
                while remaining:
                    for owner in owners:
                        while q[owner] and not q[owner][0][2]:
                            q[owner].popleft()
                        if not q[owner]:
                            raise InvalidState('scheduler oversubscribed owner')
                    step = min(remaining, *(len(q[owner][0][2]) for owner in owners))
                    rows = []
                    for owner in owners:
                        doc, off, chunk = q[owner][0]
                        rows.append((doc, owner, off, chunk[:step]))
                        q[owner][0] = [doc, off+step, chunk[step:]]
                    group, coded = self.create_group(lane, nodeset, rows, 'MIXED')
                    groups[group.id] = group
                    stage.update(coded)
                    remaining -= step
            for owner, items in q.items():
                for doc, off, data in items:
                    if data:
                        group, coded = self.create_group(lane, nodeset,
                                                         [(doc, owner, off, data)], 'STANDALONE')
                        groups[group.id] = group
                        stage.update(coded)
        manifests = {d: Document(owner, len(data), sha(data))
                     for d, (owner, data) in files.items()}
        return self.transition(groups, manifests, stage, nodes)

    def transition(self, groups, docs, stage, nodes=None, joining_node=None):
        return Transition(self.epoch, groups, docs, stage,
                          tuple(nodes if nodes is not None else self.active_nodes()),
                          joining_node)

    def visible_blob(self, ref: Fragment, staged=None, failed=()):
        if ref.node in failed or (not self.nodes[ref.node]['active']
               and not (staged is not None and ref.key in staged)):
            return None
        if staged is not None and ref.key in staged:
            data = staged[ref.key]
        else:
            data = self.nodes[ref.node]['objects'].get(ref.key)
        if data is None or sha(data) != ref.digest or len(data) != ref.size:
            return None
        return data

    def decode(self, group, staged=None, failed=(), target_rows=None):
        eligible = []
        for ref in group.refs:
            blob = self.visible_blob(ref, staged, failed)
            if blob is not None:
                eligible.append((ref.row, blob))
        if len(eligible) < group.rank:
            raise InsufficientFragments(f'{group.id}: valid {len(eligible)}, need {group.rank}')
        chosen = eligible[:group.rank]
        inv = inverse([generator(group.rank)[i] for i, _ in chosen])
        rows = range(group.rank) if target_rows is None else sorted(set(target_rows))
        result = {j: linear_rows([inv[j]], [blob for _, blob in chosen])[0] for j in rows}
        return result, sum(len(b) for _, b in chosen)

    def read(self, doc_id, failed=(), groups=None, docs=None, staged=None, stats=None):
        groups = self.groups if groups is None else groups
        docs = self.documents if docs is None else docs
        if doc_id not in docs:
            raise KeyError(doc_id)
        chunks = []
        touched = 0
        bytes_read = 0
        for group in groups.values():
            indices = [i for i, member in enumerate(group.members)
                       if member.doc == doc_id and member.real_length > 0]
            if not indices:
                continue
            source_rows, transferred = self.decode(group, staged, failed, indices)
            touched += 1
            bytes_read += transferred
            for j in indices:
                member = group.members[j]
                chunks.append((member.offset, source_rows[j][:member.real_length]))
        offset = 0
        content = bytearray()
        for pos, chunk in sorted(chunks):
            if pos != offset:
                raise InvalidState('document source spans are missing or overlapping')
            content.extend(chunk)
            offset += len(chunk)
        meta = docs[doc_id]
        if len(content) != meta.length or sha(bytes(content)) != meta.digest:
            raise InvalidState('reconstructed ciphertext checksum mismatch')
        if stats is not None:
            stats.update(groups_touched=touched, coded_bytes_read=bytes_read,
                         ciphertext_bytes=meta.length,
                         read_amplification=round(bytes_read/meta.length, 4))
        return bytes(content)

    def usage(self):
        used = defaultdict(int)
        for group in self.groups.values():
            for ref in group.refs:
                if self.nodes[ref.node]['active'] and ref.key in self.nodes[ref.node]['objects']:
                    used[ref.node] += ref.size
        return used

    @staticmethod
    def plan_binding(plan):
        # Bind both staged content AND the authoritative metadata to the check.
        parts = (plan.expected_epoch, plan.active_nodes, plan.joining_node,
                 tuple(sorted((doc, meta.owner, meta.length, meta.digest)
                              for doc, meta in plan.documents.items())),
                 tuple(sorted((gid, g.mode, g.lane, g.rank,
                     tuple((m.doc, m.owner, m.offset, m.real_length) for m in g.members),
                     tuple((r.key, r.node, r.row, r.digest, r.size) for r in g.refs))
                     for gid, g in plan.groups.items())),
                 tuple(sorted((key, sha(content)) for key, content in plan.staged.items())))
        return sha(repr(parts).encode())

    def verify(self, plan: Transition, exhaustive_failures=False):
        if not self.ledger_available:
            raise Unauthorized('metadata authority unavailable')
        if plan.expected_epoch != self.epoch:
            raise Conflict('membership/document version conflict')
        nodes = set(self.active_nodes()) | ({plan.joining_node} if plan.joining_node is not None else set())
        if set(plan.active_nodes) != nodes:
            raise Conflict('candidate membership differs')
        # Temporary storage uses old+staged bytes on each surviving target.
        used = self.usage()
        for group in plan.groups.values():
            targets = [r.node for r in group.refs]
            if len(set(targets)) != N:
                raise InvalidState('collocated coding rows')
            for ref in group.refs:
                if ref.node not in nodes:
                    raise InvalidState('fragment assigned to unavailable storage')
                if ref.key in plan.staged:
                    if sha(plan.staged[ref.key]) != ref.digest:
                        raise InvalidState('staged fragment altered')
                    used[ref.node] += ref.size
                elif self.visible_blob(ref) is None:
                    raise InvalidState('missing or damaged active fragment')
        for node, consumed in used.items():
            if consumed > self.nodes[node]['capacity']:
                raise InsufficientCapacity(f'node {node}: staging {consumed} > quota {self.nodes[node]["capacity"]}')
        for doc in plan.documents:
            # Check actual document contribution reaches all new active nodes.
            covered = {ref.node for g in plan.groups.values()
                       if any(s.doc == doc and s.real_length > 0 for s in g.members)
                       for ref in g.refs}
            if covered != nodes:
                raise InvalidState('incomplete per-document coverage')
            self.read(doc, groups=plan.groups, docs=plan.documents, staged=plan.staged)
        if exhaustive_failures:
            for pair in itertools.combinations(sorted(nodes), 2):
                # The joining node is staged but not ACTIVE yet. Simulate it
                # as active only inside this validation path.
                for d in plan.documents:
                    self.read(d, failed=pair, groups=plan.groups,
                              docs=plan.documents, staged=plan.staged)
        plan.verified = True
        plan.binding = self.plan_binding(plan)
        return plan

    def commit(self, plan: Transition):
        if not plan.verified:
            raise InvalidState('candidate not verified')
        if not self.ledger_available:
            raise Unauthorized('cannot activate without metadata authority')
        if plan.expected_epoch != self.epoch:
            raise Conflict('stale candidate')
        if plan.binding != self.plan_binding(plan):
            raise InvalidState('verified plan changed before activation')
        # Guard against mutated staged bytes between verify and commit.
        refs = {ref.key:ref for group in plan.groups.values() for ref in group.refs}
        for key, blob in plan.staged.items():
            if key not in refs or sha(blob) != refs[key].digest:
                raise InvalidState('staged fragment modified after verification')
        for group in plan.groups.values():
            for ref in group.refs:
                if ref.key in plan.staged:
                    self.nodes[ref.node]['objects'][ref.key] = plan.staged[ref.key]
        self.groups = dict(plan.groups)
        self.documents = dict(plan.documents)
        if plan.joining_node is not None:
            self.nodes[plan.joining_node]['active'] = True
        # Model cleanup follows atomic reference change. Real providers need
        # asynchronous, governed garbage collection and historical retention.
        active_keys = {ref.key for g in self.groups.values() for ref in g.refs}
        for node in self.nodes.values():
            node['objects'] = {k:b for k,b in node['objects'].items() if k in active_keys}
        self.epoch += 1
        return self.epoch

    def apply(self, plan, exhaustive_failures=False):
        self.verify(plan, exhaustive_failures)
        return self.commit(plan)

    def load(self, new: Dict[str, Tuple[str, bytes]], exhaustive_failures=False):
        current = {d:(meta.owner, self.read(d)) for d,meta in self.documents.items()}
        if any(d in current for d in new):
            raise InvalidState('duplicate immutable document')
        current.update(new)
        return self.apply(self.build(current, self.active_nodes()), exhaustive_failures)

    def delete(self, doc_id):
        if doc_id not in self.documents:
            raise KeyError(doc_id)
        groups = dict(self.groups)
        staged = {}
        for gid, old in list(groups.items()):
            if not any(s.doc == doc_id and s.real_length for s in old.members):
                continue
            del groups[gid]
            decoded, _ = self.decode(old)
            survivors = [(s.doc,s.owner,s.offset,decoded[i][:s.real_length])
                         for i,s in enumerate(old.members)
                         if s.doc != doc_id and s.real_length]
            if not survivors:
                continue
            if old.mode == 'MIXED' and len(survivors) >= 2:
                group, fragment_data = self.create_group(old.lane,
                    tuple(r.node for r in old.refs), survivors, 'MIXED')
                groups[group.id] = group
                staged.update(fragment_data)
            else:
                # A last independent owner is erasure-coded without claiming
                # cross-user mixing. Preserve the survivor's byte spans.
                for src in survivors:
                    group, fragment_data = self.create_group(old.lane,
                        tuple(r.node for r in old.refs), [src], 'STANDALONE')
                    groups[group.id] = group
                    staged.update(fragment_data)
        docs = {d:meta for d,meta in self.documents.items() if d != doc_id}
        self.apply(self.transition(groups, docs, staged))

    def withdraw(self, node_id):
        self.nodes[node_id]['active'] = False
        self.epoch += 1  # externally changed contributor status invalidates plans

    def repair(self, stats=None):
        groups = dict(self.groups)
        coded_bytes_read = 0
        coded_bytes_uploaded = 0
        stage = {}
        active = self.active_nodes()
        target_load = self.usage()
        for gid,group in list(groups.items()):
            valid = [ref for ref in group.refs if self.visible_blob(ref) is not None]
            if len(valid) < group.rank:
                raise InsufficientFragments('cannot regenerate group with insufficient intact rows')
            if len(valid) == N:
                continue
            source, transferred = self.decode(group)
            coded_bytes_read += transferred
            rows = [source[i] for i in range(group.rank)]
            replacements = {ref.row:ref for ref in valid}
            for old in group.refs:
                if old.row in replacements:
                    continue
                used = {ref.node for ref in replacements.values()}
                options = [i for i in active if i not in used]
                if not options:
                    raise InsufficientCapacity('fewer than 6 distinct active repair targets')
                dest = min(options, key=lambda i: (target_load[i], i))
                content = linear_rows([generator(group.rank)[old.row]], rows)[0]
                key = f'{self.gid()}/repair/{old.row}'
                replacements[old.row] = Fragment(key,dest,old.row,sha(content),len(content))
                stage[key] = content
                coded_bytes_uploaded += len(content)
                target_load[dest] += len(content)
            groups[gid] = CodingGroup(group.id,group.lane,group.mode,group.members,
                tuple(replacements[i] for i in range(N)),group.width,group.rank)
        if not stage:
            raise InvalidState('no damaged fragments')
        self.apply(self.transition(groups, dict(self.documents), stage))
        if stats is not None:
            stats.update(coded_bytes_read=coded_bytes_read,
                         coded_bytes_uploaded=coded_bytes_uploaded,
                         regenerated_fragments=len(stage))
        return len(stage)

    def join(self, capacity=10_000_000):
        node = max(self.nodes) + 1
        self.nodes[node] = {'capacity':capacity,'active':False,'objects':{}}
        docs = {d:(meta.owner,self.read(d)) for d,meta in self.documents.items()}
        candidate = self.build(docs, self.active_nodes()+(node,))
        candidate.joining_node = node
        self.apply(candidate)
        return node



# ---------------------------------------------------------------------------
# PHASE III SECTION B: HONEST COMPARISONS AND REAL ENCRYPTED FIXTURES
# ---------------------------------------------------------------------------

def secure_workload(sizes, prefix='D'):
    """Fixture ciphertexts only. Keys and plaintext remain OUTSIDE Engine.

    Given ciphertext targets >=28 bytes, AES-GCM adds 12-byte nonce and
    16-byte tag, so all returned ciphertext lengths equal the requested sizes.
    """
    inputs, client_secrets = {}, {}
    for i, size in enumerate(sizes):
        if size < 29:
            raise ValueError('AES-GCM test size must exceed 28 bytes')
        name = f'{prefix}{i:02d}'
        plaintext = os.urandom(size - 28)
        ciphertext, key = client_encrypt(name, plaintext)
        assert len(ciphertext) == size
        inputs[name] = (f'U{i:02d}', ciphertext)
        client_secrets[name] = (key, plaintext)
    return inputs, client_secrets


def fixed_cohort_padding_bytes(sizes):
    """Naive fixed-size cross-owner cohorts with per-cohort max padding."""
    if len(sizes) % K:
        raise ValueError('require owner count multiple of four')
    return sum(N * max(sizes[i:i + K]) for i in range(0, len(sizes), K))


def sorted_cohort_padding_bytes(sizes):
    return fixed_cohort_padding_bytes(sorted(sizes))


def independent_rs_metrics(sizes, nodes=12):
    """Comparable non-systematic RS (6,4) independently on EACH document.

    Each independent ciphertext is split over every placement lane and encoded
    into 6 shards per lane. Returns exact logical payload accounting.
    This does not produce cross-owner mixing; it does produce document coverage
    on every active node. Does NOT count package/header or ledger metadata.
    """
    layouts = Engine.lanes(tuple(range(nodes)))
    total_encoded = 0
    total_read = 0
    for size in sizes:
        if size < len(layouts):
            raise ValueError('too small for nonempty lane contribution')
        q, rem = divmod(size, len(layouts))
        for lane in range(len(layouts)):
            part = q + int(lane < rem)
            width = (part + K - 1)//K
            total_encoded += N * width
            total_read += K * width
    return {'coded_bytes':total_encoded,
            'logical_groups':len(sizes)*len(layouts),
            'logical_fragments':len(sizes)*len(layouts)*N,
            'non_systematic_read_bytes_total':total_read,
            'systematic_healthy_read_bytes_total':sum(sizes)}


def randomized_cohort_baseline(sizes, trials=200, seed=26071):
    rng = random.Random(seed)
    totals=[]
    for _ in range(trials):
        perm=list(sizes)
        rng.shuffle(perm)
        totals.append(fixed_cohort_padding_bytes(perm))
    return {'trials':trials,'seed':seed,'mean_coded_bytes':statistics.mean(totals),
            'sd_coded_bytes':statistics.stdev(totals),
            'min_coded_bytes':min(totals),'max_coded_bytes':max(totals)}



def systematic_generator(rank=4):
    """Derive systematic RS generator from the existing MDS evaluation code.

    Right-multiplying G by the inverse of its first `rank` rows converts the
    first rank encoded rows into identity/data shards while retaining MDS.
    """
    base=generator(rank)
    to_systematic=inverse(base[:rank])
    return [[_matrix_dot(row,col) for col in zip(*to_systematic)]
            for row in base]


def _matrix_dot(a,b):
    val=0
    for x,y in zip(a,b):val ^= GF.mul(x,y)
    return val


# ---------------------------------------------------------------------------
# PHASE III SECTION C: AUTOMATED CORRECTNESS, SECURITY & FAILURE TESTS
# ---------------------------------------------------------------------------

class StorageTests(unittest.TestCase):
    def test_01_aes256_gcm_and_authentication(self):
        inputs, private = secure_workload([512, 768, 1024, 2048])
        for name, (_, ciphertext) in inputs.items():
            key, plain = private[name]
            self.assertEqual(client_decrypt(name, ciphertext, key), plain)
            with self.assertRaises(InvalidTag):
                client_decrypt(name, ciphertext, AESGCM.generate_key(bit_length=256))
            corrupt = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
            with self.assertRaises(InvalidTag):
                client_decrypt(name, corrupt, key)

    def test_02_real_aead_ciphertexts_survive_cross_owner_roundtrip(self):
        inputs, secrets = secure_workload([4096]*8)
        engine = Engine()
        engine.load(inputs)
        self.assertTrue(all(g.mode == 'MIXED' for g in engine.groups.values()))
        for name, (owner, encrypted) in inputs.items():
            restored = engine.read(name)
            self.assertEqual(restored, encrypted)
            self.assertEqual(client_decrypt(name, restored, secrets[name][0]), secrets[name][1])

    def test_03_first_owner_is_independently_erasure_coded(self):
        inputs, secrets = secure_workload([512])
        engine = Engine()
        engine.load(inputs)
        self.assertEqual({g.mode for g in engine.groups.values()}, {'STANDALONE'})
        self.assertEqual({r.node for g in engine.groups.values() for r in g.refs}, set(range(12)))
        encrypted = engine.read('D00')
        self.assertEqual(client_decrypt('D00', encrypted, secrets['D00'][0]), secrets['D00'][1])

    def test_04_all_coding_submatrices_are_invertible(self):
        for rank in (2, 3, 4):
            gen = generator(rank)
            self.assertTrue(all(a != 0 for row in gen for a in row))
            for chosen in itertools.combinations(range(N), rank):
                inv = inverse([gen[j] for j in chosen])
                for i in range(rank):
                    for j in range(rank):
                        total = 0
                        for t in range(rank):
                            total ^= GF.mul(inv[i][t], gen[chosen[t]][j])
                        self.assertEqual(total, int(i == j))

    def test_05_naive_sorted_and_independent_baselines(self):
        sizes=[1024,2048,4096,8192]*3
        self.assertEqual(fixed_cohort_padding_bytes(sizes),147456)
        self.assertEqual(sorted_cohort_padding_bytes(sizes),86016)
        self.assertEqual(independent_rs_metrics(sizes)['coded_bytes'],69120)

    def test_06_adaptive_mixed_workload_and_coverage(self):
        sizes=[1024,2048,4096,8192]*3
        inputs, keys=secure_workload(sizes)
        engine=Engine()
        engine.load(inputs)
        self.assertTrue(all(g.mode=='MIXED' for g in engine.groups.values()))
        stored=sum(r.size for g in engine.groups.values() for r in g.refs)
        self.assertEqual(stored,69120)
        self.assertEqual(len(engine.groups),16)
        self.assertEqual({v for v in engine.usage().values()}, {5760})
        for name, (_, cipher) in inputs.items():
            self.assertEqual(engine.read(name),cipher)
            self.assertEqual(client_decrypt(name,cipher,keys[name][0]),keys[name][1])

    def test_07_exhaustive_12_node_failure_reconstruction(self):
        inputs,_=secure_workload([128,256,512,1024]*3)
        e=Engine();e.load(inputs)
        attempts=0
        for lost in itertools.combinations(e.active_nodes(),2):
            for name, (_, ciphertext) in inputs.items():
                self.assertEqual(e.read(name,lost),ciphertext)
            attempts+=1
        self.assertEqual(attempts,math.comb(12,2))

    def test_08_coded_fragment_integrity_and_failure_threshold(self):
        inputs,_=secure_workload([512]*4)
        e=Engine();e.load(inputs)
        group=next(iter(e.groups.values()))
        for ref in group.refs[:2]:
            data=e.nodes[ref.node]['objects'][ref.key]
            e.nodes[ref.node]['objects'][ref.key] = bytes([data[0]^1])+data[1:]
        d=group.members[0].doc
        self.assertEqual(e.read(d),inputs[d][1])
        ref=group.refs[2]
        data=e.nodes[ref.node]['objects'][ref.key]
        e.nodes[ref.node]['objects'][ref.key]=bytes([data[0]^1])+data[1:]
        with self.assertRaises(InsufficientFragments):e.read(d)

    def test_09_delete_a_document_and_keep_independent_survivors(self):
        files, secrets=secure_workload([512]*4)
        e=Engine();e.load(files);e.delete('D00')
        with self.assertRaises(KeyError):e.read('D00')
        for name in ('D01','D02','D03'):
            result=e.read(name)
            self.assertEqual(result,files[name][1])
            self.assertEqual(client_decrypt(name,result,secrets[name][0]),secrets[name][1])

    def test_10_last_owner_transitions_to_standalone(self):
        files,_=secure_workload([256]*4)
        e=Engine();e.load(files)
        for doc in ('D00','D01','D02'):e.delete(doc)
        self.assertEqual({g.mode for g in e.groups.values()}, {'STANDALONE'})
        self.assertEqual(e.read('D03'), files['D03'][1])

    def test_11_node_withdrawal_and_repair(self):
        files,_=secure_workload([512]*8)
        e=Engine();e.load(files)
        e.withdraw(0)
        for name,(_,cipher) in files.items():self.assertEqual(e.read(name),cipher)
        repair_stats={}
        repaired=e.repair(stats=repair_stats)
        self.assertGreater(repaired,0)
        self.assertGreater(repair_stats['coded_bytes_read'],0)
        self.assertGreater(repair_stats['coded_bytes_uploaded'],0)
        for failed in itertools.combinations(e.active_nodes(),2):
            for name,(_,cipher) in files.items():self.assertEqual(e.read(name,failed),cipher)

    def test_12_join_thirteenth_node_with_measured_layout(self):
        files,_=secure_workload([52]*12)
        e=Engine(capacity=100000);e.load(files)
        before=len(e.groups)
        new=e.join()
        self.assertEqual(new,12)
        self.assertGreater(len(e.groups),before)
        self.assertEqual(len(set(e.usage().values())),1)
        for name,(_,cipher) in files.items():self.assertEqual(e.read(name),cipher)

    def test_13_concurrent_epoch_fail_closed(self):
        files,_=secure_workload([256])
        e=Engine();p=e.build(files,e.active_nodes())
        e.ledger_available=False
        with self.assertRaises(Unauthorized):e.verify(p)
        e.ledger_available=True;e.apply(p)
        with self.assertRaises(Conflict):e.commit(p)

    def test_14_roll_back_on_insufficient_temporary_capacity(self):
        files,_=secure_workload([512]*4)
        e=Engine(capacity=1500);e.load(files)
        old_epoch=e.epoch
        for node,info in e.nodes.items():info['capacity']=e.usage()[node]
        with self.assertRaises(InsufficientCapacity):e.delete('D00')
        self.assertEqual(e.epoch,old_epoch)
        for name,(_,cipher) in files.items():self.assertEqual(e.read(name),cipher)

    def test_15_selective_read_and_coded_byte_accounting(self):
        files,_=secure_workload([512]*12)
        e=Engine();e.load(files)
        metrics={}
        cipher=e.read('D00',stats=metrics)
        self.assertEqual(cipher,files['D00'][1])
        self.assertLess(metrics['groups_touched'],len(e.groups))
        self.assertGreater(metrics['coded_bytes_read'],metrics['ciphertext_bytes'])

    def test_16_multiple_documents_per_user_preserve_other_files(self):
        files={}
        for owner_idx in range(8):
            for file_idx in range(2):
                doc=f'X{owner_idx}-{file_idx}'
                content,key=client_encrypt(doc,os.urandom(256+32*file_idx))
                files[doc]=(f'U{owner_idx:02d}',content)
        e=Engine();e.load(files);e.delete('X0-0')
        for doc,(_,cipher) in files.items():
            if doc!='X0-0':self.assertEqual(e.read(doc),cipher)

    def test_17_tiny_document_placement_rule(self):
        e=Engine()
        with self.assertRaises(InvalidState):e.load({'tiny':('U00',b'X')})
        self.assertFalse(e.documents)

    def test_18_all_13_node_failure_pairs_reconstruct(self):
        files,_=secure_workload([52]*12)
        e=Engine(capacity=100000);e.load(files);e.join()
        pairs=0
        for lost in itertools.combinations(e.active_nodes(),2):
            for doc,(_,cipher) in files.items():self.assertEqual(e.read(doc,lost),cipher)
            pairs+=1
        self.assertEqual(pairs,math.comb(13,2))

    def test_19_staged_data_changed_after_verification_is_rejected(self):
        files,_=secure_workload([256])
        e=Engine();p=e.build(files,e.active_nodes());e.verify(p)
        key=next(iter(p.staged));p.staged[key]=bytes([p.staged[key][0]^1])+p.staged[key][1:]
        with self.assertRaises(InvalidState):e.commit(p)
        self.assertEqual(e.epoch,0)

    def test_20_provider_outage_fails_closed(self):
        files,_=secure_workload([256])
        e=Engine();e.load(files)
        for node in tuple(e.active_nodes()):e.withdraw(node)
        with self.assertRaises(InsufficientFragments):e.read('D00')

    def test_21_nonsystematic_rows_are_linear_combinations(self):
        # This is a coding-representation test, NOT a cryptographic secrecy proof.
        samples=[os.urandom(128) for _ in range(4)]
        coded=linear_rows(generator(4),samples)
        self.assertEqual(len(coded),6)
        self.assertTrue(all(blob not in samples for blob in coded))

    def test_22_eligibility_invariant_coding_group_has_distinct_owners(self):
        e=Engine()
        rows=[('A','U01',0,b'a'*32),('B','U01',0,b'b'*32)]
        with self.assertRaises(InvalidState):e.create_group(0,tuple(range(6)),rows,'MIXED')

    def test_23_client_only_decrypts_after_engine_reconstruction(self):
        files,secrets=secure_workload([256]*4)
        e=Engine();e.load(files)
        for name,(key,plain) in secrets.items():
            self.assertEqual(client_decrypt(name,e.read(name),key),plain)
            # The test passes ONLY ciphertext to Engine; private keys stay in
            # the separate test-side `secrets` mapping. This demonstrates an
            # interface boundary, not a complete proof of deployed key isolation.

    def test_24_read_model_independent_vs_mixed(self):
        sizes=[1024]*12
        baseline=independent_rs_metrics(sizes)
        files,_=secure_workload(sizes)
        e=Engine();e.load(files)
        stats={};e.read('D00',stats=stats)
        self.assertGreater(stats['read_amplification'],1.0)
        self.assertEqual(baseline['non_systematic_read_bytes_total'],sum(sizes))

    def test_25_systematic_baseline_is_also_mds(self):
        k=4
        g=systematic_generator(k)
        self.assertEqual(g[:k], [[int(i==j) for j in range(k)] for i in range(k)])
        source=[os.urandom(112) for _ in range(k)]
        coded=linear_rows(g,source)
        self.assertEqual(coded[:k],source)
        for rows in itertools.combinations(range(6),4):
            rebuilt=linear_rows(inverse([g[i] for i in rows]),[coded[i] for i in rows])
            self.assertEqual(rebuilt,source)


    def test_26_one_mib_encrypted_document_functional_size(self):
        # Functional-scale check with actual independent AES-GCM ciphertexts.
        # This is deliberately NOT a cloud throughput benchmark.
        files, private = secure_workload([1048576]*4, prefix='L')
        engine=Engine(capacity=10000000)
        engine.load(files)
        self.assertEqual({g.mode for g in engine.groups.values()}, {'MIXED'})
        for name, (_, ciphertext) in files.items():
            restored=engine.read(name)
            self.assertEqual(restored,ciphertext)
            self.assertEqual(client_decrypt(name,restored,private[name][0]),private[name][1])



# ---------------------------------------------------------------------------
# PHASE III SECTION D: EXPERIMENTAL METRICS -- ALL COUNTS COMPUTED FROM CODE
# ---------------------------------------------------------------------------

def paired_failure_experiment(node_count, sizes):
    inputs, _ = secure_workload(sizes)
    e=Engine(capacity=100000)
    e.load(inputs)
    if node_count==13:
        e.join(capacity=100000)
    attempts=0; success=0; failures=[]
    for pair in itertools.combinations(e.active_nodes(),2):
        attempts+=1
        try:
            for doc,(_,encrypted) in inputs.items():
                assert e.read(doc,pair)==encrypted
        except (AssertionError,InsufficientFragments,InvalidState) as exc:
            failures.append({'nodes':list(pair),'reason':str(exc)})
        else:success+=1
    occ=e.usage()
    return {'node_count':len(e.active_nodes()),'tested_failure_pairs':attempts,
            'successful_pair_recoveries':success,'failed_pair_recoveries':len(failures),
            'failure_examples':failures[:3], 'active_groups':len(e.groups),
            'logical_fragments':sum(len(g.refs) for g in e.groups.values()),
            'bytes_per_node_min':min(occ.values()),'bytes_per_node_max':max(occ.values()),
            'coded_bytes_total':sum(r.size for g in e.groups.values() for r in g.refs),
            'input_ciphertext_bytes':sum(len(c) for _,c in inputs.values())}


def local_machine_info():
    cpu='unknown'
    try:
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):
                cpu=line.split(':',1)[1].strip();break
    except OSError:pass
    try:
        ram_kib=next(int(t.split()[1]) for t in Path('/proc/meminfo').read_text().splitlines()
                     if t.startswith('MemTotal:'))
    except (OSError,StopIteration):ram_kib=None
    return {'python':platform.python_version(), 'operating_system':platform.system()+' '+platform.release(),
            'cpu_model':cpu, 'logical_cpu_visible':os.cpu_count(),
            'ram_gib':round(ram_kib/1024**2,2) if ram_kib else None,
            'cryptography_version':__import__('cryptography').__version__}


def timing_stats(samples_ms):
    v=sorted(samples_ms)
    return {'runs':len(v),'mean_ms':round(statistics.mean(v),3),
            'median_ms':round(statistics.median(v),3),
            'stdev_ms':round(statistics.stdev(v),3) if len(v)>1 else None,
            'min_ms':round(v[0],3), 'max_ms':round(v[-1],3),
            'p95_nearest_rank_ms':round(v[math.ceil(.95*len(v))-1],3)}


def benchmark(quick=False):
    """Timed AES fixture operations, encoding-only, verification, cutover, read and repair.

    Pure Python GF(256). Each measured trial builds a NEW, independent state.
    Run order/scheduling/cache effects remain, so report SD and environment.
    """
    sizes=[4096,65536] if quick else [4096,65536,262144]
    repetitions=3 if quick else 5
    output=[]
    for size in sizes:
        files, keys=secure_workload([size]*12,prefix='B')
        metrics={'coding_build_ms':[],'verified_transition_ms':[],
                 'state_commit_ms':[],'single_doc_read_ms':[],
                 'repair_with_verification_ms':[],'aes256_gcm_encrypt_12_ms':[]}
        read_amplifications=[];repair_downloads=[];repair_uploads=[];fragments=[]
        for rep in range(repetitions):
            test_encryption_plaintexts=[os.urandom(size-28) for _ in range(12)]
            t0=time.perf_counter()
            for i,plain in enumerate(test_encryption_plaintexts):
                client_encrypt(f'bench-{i}',plain)
            metrics['aes256_gcm_encrypt_12_ms'].append((time.perf_counter()-t0)*1000)
            trial=Engine(capacity=1000000000)
            t0=time.perf_counter();plan=trial.build(files,trial.active_nodes())
            metrics['coding_build_ms'].append((time.perf_counter()-t0)*1000)
            t0=time.perf_counter();trial.verify(plan)
            metrics['verified_transition_ms'].append((time.perf_counter()-t0)*1000)
            t0=time.perf_counter();trial.commit(plan)
            metrics['state_commit_ms'].append((time.perf_counter()-t0)*1000)
            read_info={};t0=time.perf_counter()
            assert trial.read('B00',stats=read_info)==files['B00'][1]
            metrics['single_doc_read_ms'].append((time.perf_counter()-t0)*1000)
            read_amplifications.append(read_info['read_amplification'])
            trial.withdraw(0)
            rep_stats={};t0=time.perf_counter();n=trial.repair(stats=rep_stats)
            metrics['repair_with_verification_ms'].append((time.perf_counter()-t0)*1000)
            repair_downloads.append(rep_stats['coded_bytes_read'])
            repair_uploads.append(rep_stats['coded_bytes_uploaded'])
            fragments.append(n)
            assert trial.read('B00')==files['B00'][1]
        encoded=trial.groups
        payload=sum(ref.size for g in encoded.values() for ref in g.refs)
        input_bytes=sum(len(c) for _,c in files.values())
        output.append({'ciphertext_bytes_per_document':size,'document_count':12,
                       'total_ciphertext_bytes':input_bytes,'groups':len(encoded),
                       'fragment_instances':sum(len(g.refs) for g in encoded.values()),
                       'encoded_payload_bytes':payload,
                       'encoded_payload_ratio':round(payload/input_bytes,5),
                       'single_doc_read_amplification':statistics.median(read_amplifications),
                       'repair_download_bytes':repair_downloads[0],
                       'repair_upload_bytes':repair_uploads[0],
                       'repaired_fragments':fragments[0],
                       'timings':{k:timing_stats(v) for k,v in metrics.items()},
                       'timing_scope':'coding_build excludes verify/commit; repair includes reconstruct+verify+commit'})
    # Python-traced peak allocation in one separate non-timed exercise (the
    # tracing itself changes runtime, so never mix it with latency samples).
    probe_bytes=65536
    probe_inputs,_=secure_workload([probe_bytes]*12,'M')
    tracemalloc.start()
    probe=Engine(capacity=100000000)
    probe_plan=probe.build(probe_inputs,probe.active_nodes())
    probe.verify(probe_plan)
    probe.commit(probe_plan)
    _,peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return output, {'ciphertext_bytes_per_doc':probe_bytes,
                    'python_tracemalloc_peak_bytes':peak,
                    'note':'peak Python-traced allocation during build+verify+commit; NOT total process RSS'}


def evaluate(quick=False):
    runner=unittest.TextTestRunner(verbosity=2,stream=sys.stderr)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(StorageTests)
    cases=runner.run(suite)
    status={'executed':cases.testsRun,
            'passed':cases.testsRun-len(cases.failures)-len(cases.errors),
            'failed':len(cases.failures), 'errors':len(cases.errors),
            'all_passed':cases.wasSuccessful()}
    if not cases.wasSuccessful():
        raise SystemExit('Test suite failed. Benchmark/report not produced.')

    sizes=[1024,2048,4096,8192]*3
    inputs, keys=secure_workload(sizes,'W')
    engine=Engine(capacity=10000000)
    engine.load(inputs)
    coded_bytes=sum(ref.size for g in engine.groups.values() for ref in g.refs)
    independent=independent_rs_metrics(sizes)
    random_baseline=randomized_cohort_baseline(sizes)
    total=sum(sizes)
    read={};engine.read('W00',stats=read)
    comparison={
       'encrypted_input_bytes':total,'document_count':len(sizes),
       'sizes_bytes':sizes,
       'fixed_cohort':{'coded_bytes':fixed_cohort_padding_bytes(sizes),
                       'amplification':round(fixed_cohort_padding_bytes(sizes)/total,6)},
       'size_sorted_cohort':{'coded_bytes':sorted_cohort_padding_bytes(sizes),
                             'amplification':round(sorted_cohort_padding_bytes(sizes)/total,6)},
       'random_cohort':{'trials':random_baseline['trials'],
                        'mean_amplification':round(random_baseline['mean_coded_bytes']/total,6),
                        'sd_amplification':round(random_baseline['sd_coded_bytes']/total,6)},
       'adaptive_mixed':{'coded_bytes':coded_bytes,'amplification':round(coded_bytes/total,6),
                         'groups':len(engine.groups),
                         'fragment_instances':sum(len(g.refs) for g in engine.groups.values()),
                         'mixed_group_count':sum(g.mode=='MIXED' for g in engine.groups.values()),
                         'all_real_ciphertext':True,
                         'node_occupancy_bytes':dict(engine.usage()),
                         'sample_read':read},
       'independent_rs':{'coded_bytes':independent['coded_bytes'],
                          'amplification':round(independent['coded_bytes']/total,6),
                          'groups':independent['logical_groups'],
                          'fragment_instances':independent['logical_fragments'],
                          'sample_nonsystematic_read_amplification':round(
                              independent['non_systematic_read_bytes_total']/total,6)},
       'threefold_replication':{'coded_bytes':total*3,'amplification':3.0,
                                'note':'3 complete copies; does not satisfy every-node per-document coverage on 12 nodes'},
       'derived':{'adaptive_vs_fixed_reduction_pct':round(100*(1-coded_bytes/fixed_cohort_padding_bytes(sizes)),3),
                  'adaptive_vs_sorted_reduction_pct':round(100*(1-coded_bytes/sorted_cohort_padding_bytes(sizes)),3),
                  'adaptive_vs_independent_reduction_pct':round(100*(1-coded_bytes/independent['coded_bytes']),3),
                  'adaptive_vs_independent_fragment_reduction_pct':round(100*(1-sum(len(g.refs) for g in engine.groups.values())/independent['logical_fragments']),3)}
    }
    assert comparison['adaptive_mixed']['mixed_group_count']==comparison['adaptive_mixed']['groups']
    recovery=paired_failure_experiment(12,[128,256,512,1024]*3)
    membership=paired_failure_experiment(13,[52]*12)
    bench, memory_probe=benchmark(quick)
    return {'project':'VaultChain | Phase III — Distributed encrypted storage subsystem',
            'scope':'In-memory logical nodes and modeled metadata transitions; AES-256-GCM encrypted test inputs',
            'methods':'Non-systematic Reed-Solomon-style linear code in GF(256), n=6, preferred k=4',
            'environment':local_machine_info(),
            'correctness':status,
            'comparison':comparison,
            'failure_experiment_12_nodes':recovery,
            'membership_experiment_13_nodes':membership,
            'benchmarks':bench, 'memory_probe':memory_probe,
            'evidence_note':'Failure counts and node occupancy generated by executed loops, not literal result assignments.',
            'research_scope':'No actual blockchain execution or Google Drive I/O; no end-to-end system integration claim.'}


def main():
    parser=argparse.ArgumentParser(description='VaultChain Phase III storage engine evaluation')
    parser.add_argument('--quick',action='store_true',help='Small, fast benchmark subset')
    parser.add_argument('--json',default=None,help='Write machine-readable experimental output')
    args=parser.parse_args()
    result=evaluate(args.quick)
    if args.json:
        with open(args.json,'w',encoding='utf-8') as fd:json.dump(result,fd,indent=2)
    x=result['correctness'];com=result['comparison']
    print(f'Automated tests: {x["passed"]}/{x["executed"]}')
    print(f'Coding ratios (fixed, sorted, adaptive, independent): '
          f'{com["fixed_cohort"]["amplification"]}, {com["size_sorted_cohort"]["amplification"]}, '
          f'{com["adaptive_mixed"]["amplification"]}, {com["independent_rs"]["amplification"]}')
    print('12-node failure pairs:',result['failure_experiment_12_nodes']['successful_pair_recoveries'])
    print('13-node failure pairs:',result['membership_experiment_13_nodes']['successful_pair_recoveries'])
    for row in result['benchmarks']:
        t=row['timings']
        print(f'{row["ciphertext_bytes_per_document"]//1024:4} KiB/doc  '
              f'coding-build median {t["coding_build_ms"]["median_ms"]:.2f} ms  '
              f'verify median {t["verified_transition_ms"]["median_ms"]:.2f} ms  '
              f'read median {t["single_doc_read_ms"]["median_ms"]:.2f} ms')

if __name__=='__main__':
    main()
